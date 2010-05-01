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
    """The PUNC Collector."""

    def __init__(self, notch_client, path='./punc-repo'):
        self._lock = threading.Lock()
        self._nc = notch_client
        self._errors = []
        self._results = {}
        self._orders = collections.deque()
        self.path = path
        self.repo_path = None
        self.repo = None
        # Set of files to exclude from the commit.
        self._exclusions = None
	self._do_not_commit = False

    @property
    def errors(self):
        return self._errors[:]

    def _collection_name_matches_filter(self, name, filter):
        if filter is not None and filter.collection is not None:
            if name == filter.collection:
                return True

    def collect_config(self, config, filter=None, name=None):
        """Collects all recipes in the supplied master configuration."""
        if not self._lock.acquire(False):
            logging.debug('[%s] waiting for collection lock', name)
            self._lock.acquire()
        try:
            self.path = config.get('base_path', self.path)
            self.repo_path = config.get('master_repo_path', None)
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
            if self._exclusions:
                exclude = list(self._exclusions)
            else:
                exclude = None
            if not self._do_not_commit:
                self.commit_repository(exclude=exclude)
            else:
                logging.error('Commit aborted: no results received from Notch.')
            logging.info('[%s] completed', name)
        finally:
            self._lock.release()

    def _collect_recipes(self, config, filter=None, name=None):
        """Collects the supplied recipes configuration."""
        path = self.path
        # Paths will be created.
        c = collection.Collection(name, config, path=path)
        c.collect(self._nc, filter=filter)

        def error_result(r):
            return bool(r.error is not None)

        def ok_result(r):
            return bool(r.error is None)

        logging.debug('[%s] %d responses received for '
                      '%d recipes',
                      name, len(c.results),
                      len(config.get('recipes', [])))
        if not len(c.results):
            self._do_not_commit = True
        return self._produce_output(path, c.results, name=name)

    def commit_repository(self, message=None, exclude=None):
        self.repo.addremove()
        self.repo.commit(message=message, exclude=exclude)

    def _get_header(self, recipe):       
        return ruleset_factory.get_ruleset_with_name(recipe.ruleset).header

    def _produce_output(self, path, results, trailing_newline=True, name=None):
        files = {}
        records_written = {}
        exclusions = set()
        for result in sorted(results):
            try:
                recipe, devicename, _ = result
                our_path = os.path.join(path, recipe.path)
                if not os.path.exists(our_path):
                    logging.info('Creating path %r', our_path)
                    os.makedirs(our_path, mode=0750)

                # Write the output for this result into the right file.
                filename = os.path.join(our_path, devicename)
                if filename in files:
                    # Existing opened file.
                    f = files[filename]
                else:
                    # New file. Open it and write the header.
                    f = open(filename, 'w')
                    files[filename] = f
                    header = self._get_header(recipe)
                    if header:
                        f.write(header + '\n')

                print len(results[result] or '')
                
                if not len(recipe.errors):
                    # Write output to file.
                    f.write(results[result])
                else:
                    logging.error('[%s] Skipping file %s; incomplete results '
                                  'for device', name, filename)
                    exclusions.add(filename)
                    
            except (OSError, IOError, EOFError), e:
                logging.error('Failed writing %r. %s: %s', filename,
                              e.__class__.__name__, str(e))
                continue
        self._exclusions = exclusions

        # Write a trailing newline and close all files.
        for f in files.values():
            try:
                if trailing_newline:
                    f.write('\n')
                f.close()
            except (OSError, IOError, EOFError):
                continue
        return files
