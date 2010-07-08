# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# Copyright 2010 Andrew Fort

"""PUNC's data model."""


import copy
import logging
import os

import notch.client


class Action(object):
    """A collection Action, used to produce a Notch request."""

    def __init__(self, notch_method=None, args=None,
                 parser=None, parser_args=None, target=None, key=None):
        self.notch_method = notch_method
        self.args = args
        self.key = key
        self.parser = parser
        self.parser_args = parser_args or {}
        self.target = target

    def __repr__(self):
        # Drop .target.
        return ('%s(notch_method=%r, args=%r, parser=%r, parser_args=%r, '
                'key=%r)' %
                (self.__class__.__name__,
                 self.notch_method, self.args, self.parser, self.parser_args,
                 self.key))


class Recipe(object):
    """A collection recipe. Combines a ruleset with devices.

    The collection uses a recipe instance to generate the query schedule

    Attributes:
      name: A string, the recipe name.
      devices: An iterable of strings, device names to apply the recipe to.
      ruleset: A string, the ruleset name to use for this collection.
    """

    def __init__(self, name='UNNAMED', devices=None, ruleset=None):
        self.name = name
        self.devices = devices
        self.ruleset = ruleset

    def __repr__(self):
        return ('%s(name=%r, devices=%r, ruleset=%r)'
                % (self.__class__.__name__, self.name, self.devices,
                   self.ruleset))


class Result(object):
    """A PUNC processing result.

    Attributes:
      rule: A Rule object, the rule the Result was executed for.
      result: A notch.client.Request object, the Notch request/result object.
      key: Any hashable/sortable object, used to determine the output order.
      output: A string, the result data (or None if the result is not complete).
      status: An int [0..3], the result status. See STATUS_* class constants.
    """

    # Integer constants representing the value of the status attribute.
    # The result is not yet complete
    STATUS_PENDING = 0  
    # The request completed successfully and the result is OK
    STATUS_OK = 1  
    # The result is considered an error
    STATUS_ERROR = 2  
    # The result is not an error, but any result should not be
    # included in output.
    STATUS_IGNORE = 3
    
    _STATUSES = {0: 'STATUS_PENDING',
                 1: 'STATUS_OK',
                 2: 'STATUS_ERROR',
                 3: 'STATUS_IGNORE'}

    def __init__(self, rule, result, key, output=None, status=0):
        self.rule = rule
        self.result = result
        self.key = key
        self.output = output
        self.status = status

    def __repr__(self):
        return ('%s(rule=%r, key=%r, length=%d, status=%s.%s)' %
                (self.__class__.__name__,
                 self.rule, self.key, len(self.result.result or ''),
                 self.__class__.__name__,
                 self._STATUSES.get(self.status, 'UNKNOWN')))

    def completed(self):
        return bool(self.result is not None)

    def device_name(self):
        return self.result.arguments.get('device_name')

    def error_message(self):
        """Returns the error message from the result, or None if no error."""
        if self.result.error is None:
            return None
        else:
            try:
                return '%s: %s' % (self.result.error[0], self.result.error[1])
            except:
                return str(self.result.error)


class Rule(object):
    """A sequence of collection Actions.

    Attributes:
      handling: An int, how to determine success of the action sequence.
        See HANDLE_* class constants.
      actions: A list of Action objects, the actions in this rule.
      target: A Target object, where to write the results of this Rule.
        If None, the Ruleset Target or finally default Target is used.
    """

    # How a rule's actions results are handled.
    HANDLE_OPTIONAL = 0  # Successful response to any action is optional
    HANDLE_ALL_REQUIRED = 1  # Successful response to all actions is required
    HANDLE_ANY_REQUIRED = 2  # Successful response to at least one action
    HANDLE_FIRST_OR_ALL_OTHERS = 3 # Success on first or ALL other actions

    # String flags used
    _RESULT_HANDLING = {0: 'HANDLE_OPTIONAL',
                        1: 'HANDLE_ALL_REQUIRED',
                        2: 'HANDLE_ANY_REQUIRED',
                        3: 'HANDLE_FIRST_OR_ALL_OTHERS',
                        }

    def __init__(self, actions=None, handling=None, target=None):
        self.handling = handling or self.HANDLE_ALL_REQUIRED
        self.actions = actions or []
        self._action_status = []
        self.target = target

        # A dictionary of flags, per device, used to serialise
        # requests on an individual device name basis.
        self._done = {}
        self._stopped = False

    def __repr__(self):
        return ('%s(actions=%r, handling=%s, target=%r)' %
                (self.__class__.__name__,
                 self.actions,
                 '%s.%s' % (self.__class__.__name__,
                            self._RESULT_HANDLING[self.handling]),
                 self.target))

    @property
    def first_action_passed(self):
        """Returns True if the first action was successfully passed."""
        if len(self._action_status):
            return bool(self._action_status[0] != Result.STATUS_ERROR)
        # If there are no actions done yet, we haven't passed the first one.
        return False

    @property
    def num_actions_completed(self):
        """Returns the number of actions 'finish'ed."""
        return len(self._action_status)

    def finish(self, status):
        self._action_status.append(status)

    def request_generator(self):
        """Returns a generator for the Notch Requests in the rule."""
        # Make this method idempotent for callers.
        self._stopped = False

        for action in self.actions:
            if not self._stopped:
                target = action.target or self.target
                yield notch.client.Request(
                    action.notch_method,
                    arguments=action.args,
                    callback_args=(self, action, target))
            else:
                raise StopIteration

    def request_list(self):
        return [r for r in self.request_generator()]

    def stop(self):
        """Stops the request generator."""
        self._stopped = True


class Ruleset(object):
    """A sequence of collection rules, which are collections of actions.

    Attributes:
      name: A string, ruleset name (used as a key for the ruleset factory).
    """

    # The ruleset's name: matches the ruleset name in configuration (recipe).
    name = '__invalid__'

    # The header written to the start of the ruleset's output.
    header = ''

    def __init__(self):
        # Setup the generators now.
        self._gens = [r.request_generator() for r in self.rules()]
        self._done_gens = set()
        self.target = Target()

    def rules(self):
        """Returns a list of rules, over-ridden by concrete subclasses."""
        return []

    def requests(self, devices):
        """Generator for Notch Requests in the ruleset.

        We iterate over each of the generators (which play out a
        sequence). They will
        """
        while True:
            for i in self._gens:
                if i in self._done_gens:
                    continue
                try:
                    for req in self._request_for_devices(i.next(), devices):
                        yield req
                except StopIteration:
                    self._done_gens.add(i)
                    continue
            if len(self._gens) == len(self._done_gens):
                return

    def _request_for_devices(self, request, devices):
        requests = set()
        for d in devices:
            r = copy.copy(request)
            r.arguments['device_name'] = d
            requests.add(r)
        return requests


class Target(object):
    """A collection target template.

    Attributes:
      device_name: A string. This field must be set before name() is
        called. It is the device name (the 'centre' part of the file name).
      base_path: A string. Required to be set prior to name(), and
        prepends all paths produced by name().
      file_prefix: A string. Optional, is prepended to the device_name
        in the filename via name().
      file_suffix: A string. Optional, is appended to the device_name
        in the filename via name().
      header: A string, the text to write to the beginning of the target
        during collation (e.g., '!RANCID-CONTENT-TYPE: cisco\n!\n')
    """

    def __init__(self, device_name=None, file_prefix='',
                 file_suffix='', target_mode='', header=''):
        """Initializer.

        Args (not described in class attributes):
          target_mode: A string. Leave default (blank) for standard
            text files.  Use 'b' for binary targets.
        """
        self.device_name = device_name
        self.base_path = None
        self.header = header
        self.file_prefix = file_prefix
        self.file_suffix = file_suffix
        self._file_mode = target_mode

    def __repr__(self):
        return ('%s(device_name=%r, file_prefix=%r, file_suffix=%r, '
                'target_mode=%r)' %
                (self.__class__.__name__,
                 self.device_name, self.file_prefix, self.file_suffix,
                 self.file_mode))

    @property
    def binary(self):
        return bool(self._file_mode.lower() == 'b')

    @property
    def file_mode(self):
        return self._file_mode.lower()

    @property
    def name(self):
        """Returns the target's final destination pathname."""
        if self.device_name is None:
            raise ValueError('device_name attribute must be set')
        elif self.base_path is None:
            raise ValueError('base_path attribute must be set')
        else:
            return os.path.join(
                self.base_path, '%s%s%s' % (
                    self.file_prefix, self.device_name, self.file_suffix))

    def create_base_path(self):
        if not os.path.exists(self.base_path):
            logging.debug('Creating path %r', self.base_path)
            os.makedirs(self.base_path, mode=0755)


class TargetCache(object):
    """Keeps a cache of Target objects keyed by target creation attributes.

    This cache is used by the collector to maintain a single Target instance
    for every distinct file opened for output by the system.
    """

    def __init__(self):
        self._targets = {}

    def get(self, collection, device_name, file_prefix='',
            file_suffix='', target_mode=''):
        """Returns a Target instance from cache or by creating it."""
        key = (collection, device_name, file_prefix, file_suffix, target_mode)
        if key in self._targets:
            return self._targets[key]
        else:
            return self._new(collection, device_name, file_prefix, file_suffix,
                             target_mode)

    def _new(self, collection, device_name, file_prefix='',
             file_suffix='', target_mode=''):
        """Generates a new Target for the given keys."""
        key = (collection, device_name, file_prefix, file_suffix, target_mode)
        self._targets[key] = Target(device_name=device_name,
                                    file_prefix=file_prefix,
                                    file_suffix=file_suffix,
                                    target_mode=target_mode)
        return self._targets[key]
