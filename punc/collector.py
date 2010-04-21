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

"""The PUNC collector.

The collector provides user interface code with an API for creating
collection activities and triggering them.
"""


import collections
import logging
import operator
import Queue
import os
import re
import traceback

import eventlet

import notch.client

import collection
import ruleset_factory


class ConfigError(Exception):
    """There is an error in the configuration that prevents work continuing."""


class InvalidCollection(Exception):
    """The collection defined was invalid."""


class Collector(object):
    """The PUNC Collector.

    The collector can be sent work orders via the collect_for,
    collect_collection and collect_all methods. It operates a
    queue listener greenthread (via eventlet) that means you must
    explicitly call .stop() (via a try/finally, perhaps) on this
    instance when you're done.
    """
    # How many seconds to sleep for when the queue is empty. It also
    # sets the minimum latency when the queue is empty. As this is
    # used to encourage cooperative greentasking, the value can be
    # very small.
    EMPTY_QUEUE_SLEEP_SEC = 0.01

    # The status_event stop signal.
    STOP_EVENT = 'STOP'

    def __init__(self, notch_client, path='./tmpdata'):
        self._nc = notch_client
        self._errors = []
        self._results = {}
        self._orders = collections.deque()
        # Will be the greenthread for our queue processor. 
        self._gt = None
        self.path = path
        self.request_q = eventlet.queue.LightQueue()
        self.status_event = eventlet.event.Event()

    @property
    def errors(self):
        return self._errors[:]

    def collect_config(self, config, name='default'):
        path = self.path
        # Paths will be created.
        c = collection.Collection(name, config, path=path)
        c.collect(self._nc)
        logging.debug('Awaiting results from collection %s', name)
        self._nc.wait_all()
        logging.debug('Received %d results for collection %s', len(c.results),
                      name)
        self._produce_output(config, path, c.results)

    def collect(self, device, regexp=False, collection_name=None):
        """Collects for a device or a regexp of devices.

        Collects for either all collections, or a specific one (if
        collection_name is supplied).

        Args:
          device: A string, either a single device name, or if regexp=True,
            a regular expression matching device names.
          regexp: A boolean, if True, treat device as a regualr expression.
          collection_name: A string, a collection name to collect for the 
            given devices.
        """
        # Scan the full configurations, replacing all regexes with the
        # device name, instead.
        c = {}
        for key, collection in self.collections.items():
            for rule in collection['rules']:
                if rule.get('regexp'):
                    if not regexp:
                        rule['regexp'] = re.escape(device)
                    else:
                        rule['regexp'] = device
            c[key] = collection
        # Add to the queue.
        self.request_q.put((key, c))
        
    def stop(self):
        self.status_event.send(self.STOP_EVENT)
        if hasattr(self, '_gt') and self._gt:
            self._gt.wait()

    def _write_header(self, file_obj, rule):
        header = ruleset_factory.get_ruleset_with_name(rule.ruleset).header
        if header:
            file_obj.write(header + '\n')

    def _produce_output(self, config, path, results, trailing_newline=True):
        files = {}
        for result in sorted(results):
            try:
                rule, filename, _ = result
                our_path = os.path.join(path, rule.path)
                if not os.path.exists(our_path):
                    logging.info('Creating path %r', our_path)
                    os.makedirs(our_path, mode=0750)

                filename = os.path.join(our_path, filename)
                if filename in files:
                    f = files[filename]
                else:
                    f = open(filename, 'w')
                    files[filename] = f
                    self._write_header(f, rule)

                f.write(results[result])
            except (OSError, IOError, EOFError), e:
                logging.error('Failed writing %r. %s: %s', filename,
                              e.__class__.__name__, str(e))
                continue

        # Write a trailing newline and close all files.
        for f in files.values():
            try:
                if trailing_newline:
                    f.write('\n')
                f.close()
            except (OSError, IOError, EOFError):
                continue
                
