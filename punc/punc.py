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

import curses
import logging
import optparse
import os
import sys
import time

import notch.client

import collector
import punc_config


# A modified (output) version of the formatter from Tornado.
class _ColorLogFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        logging.Formatter.__init__(self, *args, **kwargs)
        fg_color = curses.tigetstr("setaf") or curses.tigetstr("setf") or ""
        self._colors = {
            logging.DEBUG: curses.tparm(fg_color, 4), # Blue
            logging.INFO: curses.tparm(fg_color, 2), # Green
            logging.WARNING: curses.tparm(fg_color, 3), # Yellow
            logging.ERROR: curses.tparm(fg_color, 1), # Red
        }
        self._normal = curses.tigetstr("sgr0")

    def format(self, record):
        try:
            record.message = record.getMessage()
        except Exception, e:
            record.message = "Bad message (%r): %r" % (e, record.__dict__)
        record.asctime = time.strftime(
            "%y%m%d %H:%M:%S", self.converter(record.created))
        prefix = '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d]' % \
            record.__dict__
        color = self._colors.get(record.levelno, self._normal)
        formatted = color + prefix + self._normal + " " + record.message
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            formatted = formatted.rstrip() + "\n" + record.exc_text
        return formatted.replace("\n", "\n    ")


def prettify_logging(options):
    """Turns on colored logging output for stderr iff we are in a tty."""
    if not curses: return
    try:
        if not sys.stderr.isatty(): return
        curses.setupterm()
    except:
        return
    channel = logging.StreamHandler()
    channel.setFormatter(_ColorLogFormatter())
    logging.getLogger().addHandler(channel)
    if options.debug:
        logging.getLogger().setLevel(level=logging.DEBUG)
    else:
        logging.getLogger().setLevel(level=logging.INFO)


def get_options():
    p = optparse.OptionParser()
    p.add_option('-a', '--agent', dest='agents', action='append',
                 help='Notch Agent host:port addresses', default=[])
    p.add_option('-f', '--config', dest='config',
                 help='(Mandatory) Configuration file name', default=None)
# TODO(afort): Fix filtering options.
#     p.add_option('-c', '--collection', dest='collection',
#                  help='Run only a specific named collection', default=None)
#     p.add_option('-d', '--device', dest='device',
#                  help='Collect a specific device only', default=None)
#     p.add_option('-r', '--regexp', dest='regexp',
#                  help='Collect a regexp of devices', default=None)
    p.add_option('-d', '--debug', action='store_true', dest='debug')
    return p.parse_args()


def main(argv=None):
    argv = argv or sys.argv
    options, arguments = get_options()
    prettify_logging(options)

    if not options.config:
        config = './punc.yaml'
        if not os.path.exists(config):
            config = '/etc/punc.yaml'
    else:
        config = options.config
    if not os.path.exists(config):
        config = None
    if config is None:
        logging.info('Error: No Punc configuration file found.')
        sys.exit(0)

    # Attempt to gather agent addresses from the environment.
    agents = options.agents or os.getenv('NOTCH_AGENTS')

    config_dict = punc_config.get_config_from_file(config)
    if not config_dict:
        print 'Error: No configuration loaded (see above for parse errors).'
        return 2
    try:
        logging.debug('Settuping up Notch Client')
        nc = notch.client.Connection(agents)
    except notch.client.NoAgentsError:
        print ('Error: You must supply agents via -a or '
               'the NOTCH_AGENTS environment variable.')
        return 1

    start = time.time()
    logging.info('Starting collection.')
    base_path = config_dict.get('base_path', './tmpdata')
    c = collector.Collector(nc, path=base_path)
    collections = config_dict.get('collections')
    for name, collection in collections.iteritems():
        collection_stats = c.collect_config(collection, name=name)
    logging.info('Collection completed in %.2f seconds',
                 time.time() - start)
    try:
        c.stop()
    finally:
        pass


if __name__ == '__main__':
    sys.exit(main(sys.argv))
