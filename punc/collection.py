import copy
import collections
import logging
import re
import time
import threading
import traceback

import notch.client

import ruleset_factory
from rulesets import parser


class InvalidCollectionError(Exception):
    """The collection defined was invalid."""


class ResultError(object):

    def __init__(self, error):
        self.error = error


class Recipe(object):

    def __init__(self, regexp=None, vendor=None, ruleset=None, path=None):
        self.regexp = regexp
        self.vendor = vendor
        self.ruleset = ruleset
        self.path = path
        self.results = {}
        self.errors = []

    def __repr__(self):
        return '%s(regexp=%r, vendor=%r, ruleset=%r, path=%r)' % (
            (self.__class__.__name__,
             self.regexp, self.vendor, self.ruleset, self.path))


class Collection(object):
    """A PUNC Network Configuration Collection."""

    # The maximum allowed per-command request timeout in seconds.
    DEFAULT_REQUEST_TIMEOUT_S = 120.0
    # The maximum allowed collection time in seconds.
    MAX_COLLECTION_TIMEOUT_S = 1750.0
    
    def __init__(self, name, config, path='./punc-repo',
                 notch_client=None):
        """Initialiser.

        Args:
          name: A string, the collection name.
          config: A dict, the collection config rooted at
            the name of the collection (with a 'recipes' sub-element).
          path: The base path to use for this collection.
        """
        self.name = name
        self._nc = notch_client
        self.recipes = []
        self.path = path
        self.failures = set()
        self.command_timeout_s = None

        self._devices = {}
        self._results = {}
        self._errors = {}
        self._outstanding_requests = []
        self._received_results = []
        self._finished_collection = threading.Event()

        self._parse_config(config)

    def _fix_path(self, path):
        if '..' in path:
            logging.error('Double-dot in path. Possible security violation. '
                          'Offending path is: %r', path)
            return './'
        else:
            return path

    def _parse_config(self, config):
        if not config.get('recipes'):
            raise InvalidCollectionError(
                'Collection missing recipes attribute. %r' % config)
        for recipe in config.get('recipes'):
            if not isinstance(recipe, dict):
                continue
            path = self._fix_path(recipe.get('path', self.path))
            self.recipes.append(Recipe(regexp=recipe.get('regexp'),
                                   vendor=recipe.get('vendor'),
                                   ruleset=recipe.get('ruleset'),
                                   path=path))
        self.command_timeout = config.get('command_timeout',
                                          self.DEFAULT_REQUEST_TIMEOUT_S)
        self.collection_timeout = config.get('collection_timeout',
                                             self.MAX_COLLECTION_TIMEOUT_S)                                              

    @property
    def results(self):
        """Get the results once all network requests are done."""
        return self._results

    def _device_matches_name_or_regexp(self, device_name,
                                       name=None, regexp=None):
        if name is None:
            return bool(regexp.match(device_name))
        elif regexp is None:
            return bool(name == device_name)

    def _requests(self, filter=None):
        """Generates all the Notch requests for the collection."""
        reqs = []
        for recipe in self.recipes:
            # Get device info on the devices matching our regexp.
            devices = self._nc.devices_info(recipe.regexp)
            # Update our device knowledge for later reference.
            self._devices.update(devices)
            notch_requests = self._get_requests(recipe, filter,
                                                *devices.keys())
            if len(notch_requests):
                reqs.extend(notch_requests)

        return reqs

    def collect(self, filter=None):
        """Executes the collection with a Notch Client instance."""
        logging.info('[%s] started', self.name)
        start = time.time()
        self._devices = {}
        self._outstanding_requests = self._requests(filter)
        # Send all the requests.
        if len(self._outstanding_requests):
            logging.info('[%s] Sending %d requests', self.name,
                         len(self._outstanding_requests))
            self._nc.exec_requests(self._outstanding_requests)
            end = time.time()
            logging.info('[%s] %d requests sent in %.2fs',
                         self.name, len(self._outstanding_requests), end-start)
            # Now wait for the requests to return.
            try:
                self._nc.wait_all()
            except notch.client.TimeoutError, e:
                logging.error(
                    '[%s] Timed out waiting for responses after %.2fs',
                    self.name, self.collection_timeout)
        else:
            logging.warn('[%s] No work to do', self.name)

    def _wait_for_outstanding_requests(self, timeout=None):
        """Waits until all results have returned from Notch."""
        self._finished_collection.wait(timeout=timeout)
        if not self._finished_collection.isSet():
            logging.error('[%s] Timed out waiting for responses after %.2fs',
                          self.name, timeout)
	else:
            logging.debug('[%s] Received all responses', self.name)

    def _get_requests(self, recipe, filter, *devices):
        """Generates notch requests for the current recipe and devices."""
        reqs = []
        try:
            ruleset = ruleset_factory.get_ruleset_with_name(recipe.ruleset)
        except KeyError, exc:
            logging.debug('[%s] No ruleset for device type %s', self.name, exc)
            return reqs

        for action in ruleset.actions:
            for device in devices:
                if filter:
                    if filter.device and filter.device != device:
                        logging.debug('SKIP %s != %s', filter.device, device)
                        continue
                    if filter.regexp and not bool(
                        re.compile(filter.regexp).match(device)):
                        logging.debug('SKIP re %s != %s', filter.regexp, device)
                        continue
                d = self._devices.get(device)
                if d:
                    device_vendor = d.get('device_type')
                else:
                    # Effectively skip this device in the following check.
                    device_vendor = None

                if device_vendor != recipe.vendor:
                    logging.debug('SKIP vendor %s != %s', recipe.vendor,
                                  device_vendor)
                    continue
                else:
                    args = copy.copy(action.args)
                    args['device_name'] = device
                    r = notch.client.Request(action.notch_method, args,
                                             callback=self._request_callback,
                                             callback_args=(recipe, action),
                                             timeout_s=self.command_timeout_s)
                    reqs.append(r)

        logging.debug('[%s] Generated %d requests for %r',
                      self.name, len(reqs), recipe)
        return reqs

    def _request_callback(self, r, *args, **kwargs):
        """The request callback as called by the Notch client.

        Args:
          r: A notch.client.Request object containing the error or result.
          args: A tuple of arguments used by this callback; expected tuple
            is a (Recipe, rulesets.ruleset.Ruleset) tuple being the
            source recipe and the specific ruleset which generated the request.
        """
        self._received_results.append(r)
        try:
            recipe, action = args
            device_name = r.arguments.get('device_name')
            if r.error is not None:
                # Result was an error.
                if r.error.args[1].startswith('ERROR '):
                    error_msg = r.error.args[1].split(':', 1)[1].strip()
                else:
                    error_msg = str(r.error)
                logging.error(
                    '[%s] %s: %s: %s',
                    self.name, device_name, r.error.args[0], error_msg)
                recipe.errors.append((device_name, action, error_msg))
                self._add_error(device_name, action, error_msg)
            else:
                # Result was OK.
                # The result may still be an error, if the parser fails.
                try:
                    if action.parser is not None:
                        p = action.parser(r.result)
                        parsed_result = p.Parse()
                        if parsed_result.endswith('\n'):
                            parsed_result = parsed_result[:-1]
                    else:
                        # Results without a parser (e.g., binary file transfers)
                        parsed_result = r.result
                except parser.IgnoreResultError, e:
                    logging.debug('[%s] %s: Ignoring parser result.',
                                 self.name, device_name)
                except parser.DeviceReportedError, e:
                    logging.debug('[%s] %s: Device reported error for command.',
                                 self.name, device_name)
                    self._add_error(device_name, action, str(e))

                except Exception, e:
                    logging.error(
                        'Produced an error during parsing. Traceback:')
                    logging.error(traceback.format_exc())
                    logging.error('Ignoring this result.')
                    self._add_error(device_name, action,
                                    '%s: %s' % (e.__class__.__name__, str(e)))
                else:
                    # If we haven't exited due to error, set the result.
                    self._results[(recipe, device_name,
                                   action.order, action)] = parsed_result
        finally:
            # Set completion status if we've received everything.
            if len(self._received_results) == len(self._outstanding_requests):
                self._finished_collection.set()
            # Remove reference to the received results to save memory.
            del self._received_results
            self._received_results = []

    def _add_error(self, device_name, action, error_msg):
        """Records an error for later reporting."""
        if device_name in self._errors:
            self._errors[device_name].append((action, error_msg))
        else:
            self._errors[device_name] = [(action, error_msg)]

    @property
    def devices_with_errors(self):
        """Returns a list of devices that had errors."""
        return self._errors.keys()

    @property
    def devices_without_errors(self):
        """Returns a list of devices that did not have errors."""
        all = set(self._devices.keys())
        err = set(self._errors.keys())
        return list(all - err)

    @property
    def num_total_errors(self):
        """Returns the number of errors in this collection."""
        i = 0
        for unused_dev, error_l in self._errors.items():
            i += len(error_l)
        return i

    def errors(self):
        """Returns the errors dictionary."""
        return self._errors
