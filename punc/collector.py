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

from rulesets import cisco
from rulesets import dasan_nos
from rulesets import telco
from rulesets import timetra

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
            if not self._collections:
                logging.error('No work to do; specify a device, '
                              'regexp or collection. See --help')
                return
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
                self._commit()
            else:
                logging.error('Commit aborted: no results received from Notch.')
        finally:
            self._lock.release()

    def _collection_matches_filter(self, collection, f):
        if f is not None:
            if collection == f.collection:
                return True
            if isinstance(f.collection, str) and f.collection == 'all':
                return True
        return False

    def _commit(self, message=None):
        """Commits changes to the Mercurial repository."""
        repo = rc_hg.MercurialRevisionControl(self.repo_path,
                                              self.path)
        repo.addremove()
        repo.commit(message=message)

    def error_report(self):
        rep = []
        report = False
        for c in self._collections:
            rep.append('Error report for collection %s' % c.name)
            errs = c.errors()
            for device in sorted(errs.keys()):
                rep.append('  %s:' % device)
                error_set = set()
                for e in errs.get(device):
                    action, err = e
                    error_set.add(err)
                for err in error_set:
                    rep.append('   %s' % err)
                    report = True
                rep.append('')
            rep.append('')
        if report:
            return '\n'.join(rep)

    def _result_counts(self):
        result_counts = {}
        for c in self._collections:
            for key in sorted(c.results):
                recipe, device_name, result_order = key
                path = os.path.join(self.path, recipe.path, device_name)
                if path in result_counts:
                    result_counts[path] += 1
                else:
                    result_counts[path] = 1
        return result_counts

    def _collate(self):
        results = {}
        removals = set()
        counts = self._result_counts()

        for c in self._collections:
            for key in sorted(c.results):
                recipe, device_name, result_order = key
                value = c.results[key]
                path = os.path.join(self.path, recipe.path, device_name)
                ruleset = ruleset_factory.get_ruleset_with_name(recipe.ruleset)
                if path in counts and counts[path] != len(ruleset.actions):
                    logging.error('Skipping %s (incomplete results)',
                                  device_name)
                else:
                    if path in results:
                        results[path].append(value)
                    else:
                        if ruleset.header:
                            results[path] = [ruleset.header, value]
                        else:
                            results[path] = [value]
        return results

    def _write(self, trailing_newline=True):
        """Writes collection results to disk."""
        results = self._collate()
        # Remember file objects for reuse.
        self._file_objects = {}
        for r in results:
            try:
                path = r[:r.rfind(os.path.sep)]
                if not os.path.exists(path):
                    logging.warn('Creating directory %s', path)
                    os.makedirs(path, mode=0750)
                f = self._file_objects.get(r)
                if f is None:
                    f = open(r, 'w')
                    self._file_objects[r] = f
                # Strip trailing newlines in the blocks (to avoid additional
                # newlines appearing in the output)
                if results[r][-1].endswith('\n'):
                    results[r][-1] = results[r][-1][:-1]
                # Write the output to the file object.
                f.write('\n'.join(results[r]))
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
