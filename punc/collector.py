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
import threading
import time

import eventlet

import notch.client

import collection
import rc_hg
import ruleset_factory


class ConfigError(Exception):
    """There is an error in the configuration that prevents work continuing."""


class InvalidCollection(Exception):
    """The collection defined was invalid."""


CollectorFilter = collections.namedtuple('CollectorFilter',
                                         'collection device regexp')


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
        self._lock = threading.Lock()
        self._nc = notch_client
        self._errors = []
        self._results = {}
        self._orders = collections.deque()
        self.path = path
        self.repo_path = None
        self.request_q = eventlet.queue.LightQueue()
        self.status_event = eventlet.event.Event()
        self.repo = None

    @property
    def errors(self):
        return self._errors[:]

    def _collection_name_matches_filter(self, name, filter):
        if filter is not None and filter.collection is not None:
            if name == filter.collection:
                return True

    def collect_config(self, config, filter=None, name=None):
        """Collects all recipes in the supplied master configuration."""
        self._lock.acquire()
        try:
            self.path = config.get('base_path', self.path)
            self.repo_path = config.get('repo_path', None)
            self.repo = rc_hg.MercurialRevisionControl(self.repo_path,
                                                       self.path)
            collections = config.get('collections', {})
            stats = {}
            for name, recipes in collections.iteritems():
                if filter:
                    if not self._collection_name_matches_filter(name, filter):
                        continue
                stats[name] = self._collect_recipes(recipes,
                                                    filter=filter, name=name)
            self.commit_repository()
            logging.info('[%s] completed', name)
        finally:
            self._lock.release()

    def _collect_recipes(self, config, filter=None, name=None):
        """Collects the supplied recipes configuration."""
        path = self.path
        # Paths will be created.
        c = collection.Collection(name, config, path=path)
        start = time.time()
        c.collect(self._nc, filter=filter)
        end = time.time()
        self._nc.wait_all()
        logging.debug('[%s] %d responses received for %d recipes',
                      name, len(c.results), len(config.get('recipes', [])))
        return self._produce_output(path, c.results)

    def commit_repository(self, message=None):
        self.repo.addremove()
        self.repo.commit(message=message)

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

    def _get_header(self, rule):       
        return ruleset_factory.get_ruleset_with_name(rule.ruleset).header

    def _produce_output(self, path, results, trailing_newline=True):
        files = {}
        for result in sorted(results):
            try:
                rule, filename, _ = result
                our_path = os.path.join(path, rule.path)
                if not os.path.exists(our_path):
                    logging.info('Creating path %r', our_path)
                    os.makedirs(our_path, mode=0750)

                # Write the output for this result into the right file.
                filename = os.path.join(our_path, filename)
                if filename in files:
                    # Existing opened file.
                    f = files[filename]
                else:
                    # New file. Open it and write the header.
                    f = open(filename, 'w')
                    files[filename] = f
                    header = self._get_header(rule)
                    if header:
                        f.write(header + '\n')

                # Write output to file.
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
        return files
