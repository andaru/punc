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

"""PUNC's command/data collector."""


import logging
import operator
import os
import time
import threading

import notch.client

import punc.model
import punc.parser
import punc.ruleset_factory


class Collection(object):
    """A PUNC collection for an individual recipe."""

    DEVICE_IDLE_TIMEOUT = 300.0
    DEVICE_IDLE_TIMEOUT_SAFETY_FACTOR = 0.8

    def __init__(self, recipe, base_path, notch_client,
                 command_timeout, collection_timeout):
        """Initialiser.

        Args:
          recipe: A model.Recipe object, the collection recipe.
          base_path: The base path to use for this collection.
          notch_client: A notch.client.Connection object, the Notch connection.
          command_timeout: A float, the per-command timeout in seconds.
          collection_timeout: A float, the collection timeout in seconds.
        """
        self.recipe = recipe
        self.base_path = base_path
        self.command_timeout = command_timeout
        self.collection_timeout = collection_timeout
        self.results = {}
        self.num_resp_target = 0
        self.num_resp_received = 0
        self.completed_sending = False
        self._nc = notch_client
        self._complete = threading.Event()
        self._target_cache = punc.model.TargetCache()
        # Device idle flags
        self._idle = {}

    def __repr__(self):
        return ('%s(recipe=%s, base_path=%s, command_timeout=%d, '
                'collection_timeout=%d)' %
                (self.__class__.__name__,
                 self.recipe, self.base_path, self.command_timeout,
                 self.collection_timeout))
                    
    @property
    def completed(self):
        return self._complete.isSet()

    @property
    def name(self):
        return self.recipe.name

    def collect(self):
        """Executes the collection."""
        try:
            ruleset = punc.ruleset_factory.get_ruleset(self.recipe.ruleset)
            self._ruleset = ruleset
            logging.debug('[%s] Using %s', self.recipe.name, self.recipe)
        except KeyError, exc:
            logging.error('[%s] Problem: No ruleset with name %s for %s',
                          self.recipe.name, exc, self.recipe)
            return

        self._start = time.time()
        logging.info('[%s] collection started for %d devices',
                     self.recipe.name, len(self.recipe.devices))
        for request in ruleset.requests(self.recipe.devices):
            device_name = request.arguments.get('device_name')
            self.num_resp_target += 1
            self._nc.exec_request(request, callback=self._notch_callback)
            self.device_start(device_name)

        elapsed = max(time.time() - self._start, 0)
        logging.info('[%s] %d requests sent in %.2fs',
                     self.recipe.name, self.num_resp_target, elapsed)
        self.completed_sending = True

    def device_start(self, device):
        flag = self._idle.get(device)
        if flag is None:
            logging.debug('DEVICE %s', device)
            flag = threading.Event()
            self._idle[device] = flag
            flag.set()

        logging.debug('DEVICE_WAIT %s', device)
        start = time.time()
        flag.wait(float(self.DEVICE_IDLE_TIMEOUT *
                        self.DEVICE_IDLE_TIMEOUT_SAFETY_FACTOR))
        end = time.time()
        logging.debug('DEVICE_WAIT_DONE %s (%.2fs)', device, end-start)
        if not flag.isSet():
            logging.error('DEVICE_TIMEOUT %s (%.1fs)',
                          device, self.DEVICE_IDLE_TIMEOUT)
        flag.clear()

    def device_finish(self, device):
        flag = self._idle.get(device)
        if flag is not None:
            logging.debug('DEVICE_FINISH %s', device)
            flag.set()

    def _get_error_status(self, rule):
        """Returns the rule status for of an errored result."""
        status = punc.model.Result.STATUS_PENDING
        if rule.handling == punc.model.Rule.HANDLE_ALL_REQUIRED:
            rule.stop()
            status = punc.model.Result.STATUS_ERROR
        elif rule.handling == punc.model.Rule.HANDLE_FIRST_OR_ALL_OTHERS:
            rule.stop()
            if rule.num_actions_completed > 0 and rule.first_action_passed:
                stauts = punc.model.Result.STATUS_OK
            else:
                status = punc.model.Result.STATUS_ERROR
        return status

    def _get_error_status_and_result(self, r, action):
        """Produces status and result from parser."""
        device_name = r.arguments.get('device_name')
        status = punc.model.Result.STATUS_PENDING
        try:
            if action.parser is not None:
                output = action.parser(r.result).parse()
            else:
                output = r.result[:]
            logging.debug('ACTION %s %s', device_name, action)
            status = punc.model.Result.STATUS_OK
        except punc.parser.SkipResult, e:
            status = punc.model.Result.STATUS_IGNORE
            output = None
        except punc.parser.DeviceReportedError, e:
            status = punc.model.Result.STATUS_ERROR
            output = None
        return status, output

    def _notch_callback(self, r, *args, **unused_kwargs):
        """Notch request callback."""
        self.num_resp_received += 1
        rule, action, target = args
        target = target or self._ruleset.target
        device_name = r.arguments.get('device_name')

        target_inst = self._target_cache.get(
            self, device_name, target.file_prefix,
            target.file_suffix, target.file_mode)
        target_inst.base_path = self.base_path
        target_inst.header = self._ruleset.header

        status = punc.model.Result.STATUS_PENDING
        output = None
        try:
            if r.error is not None:
                status = self._get_error_status(rule)
            else:
                status, output = self._get_error_status_and_result(r, action)
        finally:
            self.device_finish(device_name)
            result = punc.model.Result(rule, r, action.key,
                                       output=output, status=status)
            logging.debug('RESULT %s %s', r.arguments.get('device_name'),
                          result)

            if target_inst in self.results:
                self.results[target_inst].append(result)
            else:
                self.results[target_inst] = [result]

            # Are we there, yet?
            if self.finished():
                self._complete.set()
                elapsed = max(time.time() - self._start, 0)
                logging.info('[%s] Completed collection in %.1fs',
                             self.recipe.name, elapsed)

    def finished(self):
        """Returns True if this Collection is finished."""
        return bool(self.completed_sending and
                    self.num_resp_target == self.num_resp_received)

    def devices_with_errors(self):
        """Returns a list with devices having errors during collcetion."""
        devices = set()
        for results in self.results.itervalues():
            for result in results:
                if result.status == punc.model.Result.STATUS_ERROR:
                    devices.add(result.device_name())
        return sorted(devices)

    def errors(self):
        """Returns a dictionary of the errors encountered for each device."""
        errs = {}
        for results in self.results.itervalues():
            for result in results:
                if result.status == punc.model.Result.STATUS_ERROR:
                    err_msg = result.error_message()
                    if err_msg is not None:
                        name = result.device_name()
                        if name in errs:
                            errs[name].add(err_msg)
                        else:
                            errs[name] = set([err_msg])
        return errs


class Collator(object):
    """Collects and orders Collection data, then writes it.

    collate and get_file_object are not thread safe.
    """

    def __init__(self):
        self._collections = []
        self._file_objects = {}
        self._started_files = set()

    def add_collection(self, collection):
        self._collections.append(collection)

    def get_file_object(self, target):
        filename = target.name
        file_obj = self._file_objects.get(filename)
        if file_obj is None:
            target.create_base_path()
            file_obj = open(filename, 'w' + target.file_mode)
            self._file_objects[filename] = file_obj
        return file_obj

    def _results_to_write(self, results):
        """Returns a list of results that are to be written."""
        return [r for r in results if r.status == punc.model.Result.STATUS_OK]

    def collate(self):
        """Collates and writes the outputs to disk."""
        files_seen = set()
        for c in self._collections:
            for target, results in c.results.iteritems():
                results = self._results_to_write(results)
                if len(results):
                    target_file = self.get_file_object(target)

                    if target_file.name not in self._started_files:
                        logging.debug('OUTPUT_FILE_NEW %s', target_file.name)
                        self._started_files.add(target_file.name)
                        if target.header:
                            target_file.write(target.header)
                    for result in sorted(
                        results, key=operator.attrgetter('key')):
                        if result.output is not None:
                            files_seen.add(target_file)
                            logging.debug('OUTPUT %s: %r [%d bytes]',
                                          target_file.name, result.key,
                                          len(result.output))
                            target_file.write(result.output)
        logging.debug('Wrote %d output files', len(files_seen))
        # Close the files we wrote to.
        self._close_files(files_seen)

    def _close_files(self, files_seen):
        """Closes all opened files in the iterable supplied."""
        for f in files_seen:
            if not f.closed:
                f.close()

    def errors(self):
        """Returns the errors by device."""
        errors = {}
        for c in self._collections:
            for _, results in c.results.iteritems():
                for r in results:
                    dev_name = r.device_name()
                    if r.status == punc.model.Result.STATUS_ERROR:
                        if dev_name in errors:
                            errors[dev_name].add(r.error_message())
                        else:
                            errors[dev_name] = set([r.error_message()])
        return errors


def error_report(errors):
    """Returns a string error report useful for display or writing to disk."""
    rep = ['PUNC Collection Errors:', '']
    
    for device in sorted(errors.keys()):
        rep.append('  %s:' % device)
        for err in sorted(errors[device]):
            rep.append('    %s' % err)
        rep.append('')
    return '\n'.join(rep)
            
        
