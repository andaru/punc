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

    def __init__(self, notch_client, filter=None, config=None):
        config = config or {}
        # A CollectorFilter instance.
        self.filter = filter
        self.path = config.get('base_path')
        self.repo_path = config.get('master_repo_path')
        self.collections = config.get('collections')
        # Our sequence of collection objects.
        self._collections = []

        # Set of files to exclude from the commit.
        self._exclusions = None
        self.total_results = 0 

        self._lock = threading.Lock()
        self._nc = notch_client
        self._errors = []
        self._results = {}
        # A cache of file objects by path, considered held from
        # instantiation time through to completion of collection.
        self._file_objects = {}

        self.setup()

    def setup(self):
        for name, recipes in self.collections.iteritems():
            if (self.filter and
                not self._collection_matches_filter(name, self.filter)):
                continue
            else:
                c = collection.Collection(name, recipes, path=self.path,
                                          notch_client=self._nc)
                self._collections.append(c)
           
    def collect(self):
        """Collects all collections in the supplied configuration."""
        if not self._lock.acquire(False):
            logging.debug('waiting for running collection to complete')
            self._lock.acquire()
        try:
            # Collect results.
            for c in self._collections:
                coll_start = time.time()
                c.collect(filter=self.filter)
                logging.debug('[%s] %d responses (%d errors on %d devices) '
                              'received for %d recipes',
                              c.name, len(c.results), c.num_total_errors,
                              len(c.devices_with_errors),
                              len(c.recipes))
                logging.info('[%s] completed in %.2fs', c.name,
                             time.time() - coll_start)
                self.total_results += len(c.results)

            if self.total_results:
                # Write.
                self._write()
                # Commit.
                exclude = self._devices_to_exclude() or None
                self._commit(exclude=exclude)
            else:
                logging.error('Commit aborted: no results received from Notch.')
        finally:
            self._lock.release()

    def _collection_matches_filter(self, collection, f):
        if f is not None and f.collection is not None:
            if collection == f.collection:
                return True

    def _commit(self, message=None, exclude=None):
        """Commits changes to the Mercurial repository."""
        if exclude:
            if len(exclude) > 20:
                s = ' (first 20)'
            else:
                s = ''

            logging.debug('Commit will exclude devices%s: %s', s,
                          ' '.join(exclude[:20]))

        # Setup the repo, make changes and commit.
        repo = rc_hg.MercurialRevisionControl(self.repo_path,
                                              self.path)
        repo.addremove()
        repo.commit(message=message, exclude=exclude)

    def _devices_to_exclude(self):
        devices_with_errors = set()
        for c in self._collections:
            dwe = c.devices_with_errors
            if dwe:
                devices_with_errors = devices_with_errors.union(dwe)
        return sorted(list(devices_with_errors))

    def _error_report(self):
        rep = []
        for c in self._collections:
            rep.append('Collection %s' % c.name)
            for device in sorted(c.errors.keys()):
                rep.append('  %s:' % device)
                for err in c.errors.get(device):
                    rep.append('    %r' % err)
        return '\n'.join(rep)

    def _write(self, trailing_newline=True):
        """Writes collection results to disk."""
        for c in self._collections:
            devices_with_errors = c.devices_with_errors
            for result in sorted(c.results):
                recipe, device_name, _ = result
                if device_name in devices_with_errors:
                    logging.error(
                            '[%s] Skipping device %s; incomplete results for '
                            'device', c.name, device_name)
                    continue
                else:
                    try:
                        our_path = os.path.join(self.path, recipe.path)
                        if not os.path.exists(our_path):
                            logging.warn('Creating directory %s', our_path)
                            os.makedirs(our_path, mode=0750)

                        filename = os.path.join(our_path, device_name)

                        if filename in self._file_objects:
                            f = self._file_objects[filename]
                        else:
                            f = open(filename, 'w')
                            self._file_objects[filename] = f
                            header = ruleset_factory.get_ruleset_with_name(
                                recipe.ruleset).header
                            if header:
                                f.write(header + '\n')

                        f.write(c.results[result])
                    except (OSError, IOError, EOFError), e:
                        logging.error('Failed writing %r. %s: %s', filename,
                                      e.__class__.__name__, str(e))
                        continue

        # Close file objects and remove references to them.
        for f in self._file_objects.values():
            try:
                if trailing_newline:
                    f.write('\n')
                f.close()
            except (OSError, IOError, EOFError):
                continue
        self._file_objects = {}
