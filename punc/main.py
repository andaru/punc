#!/usr/bin/env python

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

"""PUNC: Pick Up (Your) Network Configuration.

punc attempts to be a flexible alternative to RANCID, whilst offering
limited device support and an absolute minimum of command output yet.
"""

import logging
import os
import sys

import punc.collect
import punc.config
import punc.model
import punc.rc_hg
import punc.util

from eventlet.green import time


def determine_config_file_path(options):
    config_path_options = [os.path.join('/etc', 'punc.yaml'),
                           os.path.join('/opt', 'local', 'etc', 'punc.yaml'),
                           os.path.join('/usr', 'local', 'etc', 'punc.yaml'),
                           os.path.join('/usr', 'local', 'etc',
                                        'punc', 'punc.yaml'),
                           ]

    if options.config:
        return options.config
    else:
        for config_path in config_path_options:
            logging.debug('Looking for PUNC config in %s',
                          config_path)
            if os.path.exists(config_path):
                return config_path
        return None


def commit_changes(repo_path, base_path):
    """Commits changes to the Mercurial repository."""
    repo = punc.rc_hg.MercurialRevisionControl(repo_path, base_path)
    repo.addremove()
    repo.commit()


def write_error_report(path, report):
    try:
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        f = open(path, 'w')
    except (OSError, IOError), e:
        logging.error('Could not write error report to %r: %s',
                      path, str(e))
    else:
        f.write(report)
        f.close()


def wait_running(nc):
    """Wait for running eventlet greenthreads.

    Eventlet sometimes has running greenthreads after waitall() returns.
    This requires a greened time module (so as not to block the I/O loop).
    """
    while nc.num_requests_running:
        nc.wait_all()
        time.sleep(0.5)


def main(argv=None):
    start = time.time()
    argv = argv or sys.argv
    options, _ = punc.util.get_options()
    punc.util.prettify_logging(options)

    # Attempt to gather agent addresses from the environment.
    agents = options.agents or os.getenv('NOTCH_AGENTS')

    # Load the configuration.
    try:
        config = determine_config_file_path(options)
        if config is None:
            logging.error('No PUNC configuration supplied. See --help')
            return 2
        config_dict = punc.config.get_config_from_file(config)
    except punc.config.Error, e:
        logging.error('Error parsing configuration')
        logging.error('%s: %s', e.__class__.__name__, str(e))
        return 2

    else:
        nc = punc.util.get_notch_client(agents)
        if nc is None:
            return 3
        collections = punc.util.build_collections(options, config_dict, nc)
        collator = punc.collect.Collator()

    logging.info('Starting network element backup')

    for collection in collections:
        collection.start()

    logging.debug('Collections done; waiting for remaining Notch callbacks.')
    wait_running(nc)
    
    for collection in collections:
        collator.add_collection(collection)
    logging.debug('Collating and writing output')
    collator.collate()
    errors = collator.errors()
    if errors:
        report = punc.collect.error_report(errors)
        logging.error(report)
        error_report_path = config_dict.get('error_report_path')
        if error_report_path:
            error_report_path = os.path.join(config_dict.get('base_path'),
                                             error_report_path)
            write_error_report(error_report_path, report)

    commit_changes(
        config_dict.get('master_repo_path'),
        config_dict.get('base_path'))

    logging.info('PUNC finished in %.2f seconds',
                  time.time() - start)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
