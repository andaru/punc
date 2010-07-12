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

"""Utility functions used by PUNC."""


import curses
import logging
import optparse
import os
import sys
import time
import traceback

import notch.client

import punc.model


# Constants
DEFAULT_COLLECT_TIMEOUT_S = 1750.0
DEFAULT_COMMAND_TIMEOUT_S = 180.0


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
        prefix = '%(levelname)1.1s%(asctime)s %(module)s:%(lineno)d|' % \
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
                 help='Configuration file name', default=None)
    p.add_option('-c', '--collection', dest='collection',
                 help='Run only a specific named collection.', default=None)
    p.add_option('-n', '--device', dest='device',
                 help='Collect a specific device name only', default=None)
    p.add_option('-r', '--regexp', dest='regexp',
                 help='Collect a regexp of devices', default=None)
    p.add_option('-d', '--debug', action='store_true', dest='debug')
    return p.parse_args()


def filter_devices(devices, vendor=None):
    """Returns a set of the keys of the dict devices, filtered by vendor.

    Args:
      devices: A dictionary as retrieved from Notch's devices_info method.
      vendor: A string or None. If a string, return only devices matching
        this vendor. If None, perform no filtering.

    Returns:
      A set of strings, hostnames matching the vendor provided.
    """
    result = set()
    for d in devices.iterkeys():
        if devices[d] is None or d is None:
            logging.warning('filter_devices skipping bad device %r=%r',
                            d, devices[d])
            continue
        if not vendor or devices[d].get('device_type') == vendor:
            result.add(d)
    return result


def get_devices(notch_client, device_regexp):
    try:
        return notch_client.devices_info(device_regexp)
    except Exception, e:
        logging.error('Notch Query error. Skipping this query. Details:')
        logging.error('%s: %s', e.__class__.__name__, str(e))
        logging.debug('%s', traceback.format_exc())
        return None


def build_collections(options, config, notch_client):
    base_path = config.get('base_path')
    master_repo_path = config.get('master_repo_path')
    _collections = config.get('collections')
    command_timeout = config.get('command_timeout', DEFAULT_COMMAND_TIMEOUT_S)
    collect_timeout = config.get('collect_timeout', DEFAULT_COLLECT_TIMEOUT_S)
    collections = []

    for name, recipes in _collections.iteritems():
        logging.debug('Found collection %r (length %d)', name, len(recipes))
        if len(recipes) > 1:
            logging.error('Collection %r has more than one recipe')
        
        recipe = recipes[0]

        if options.collection is not None and name != options.collection:
            logging.debug('Collection name mismatch. Config: %s Found: %s',
                          name, options.collection)
            continue

        device_regexp = recipe.get('regexp', r'^.*$')
        _devices = get_devices(notch_client, device_regexp)
        if not _devices:
            logging.error('No devices found for recipe %r', name)
            continue
        else:
            vendor = recipe.get('vendor')
            ruleset = recipe.get('ruleset')
            path = recipe.get('path') or ''

            final_path = os.path.join(base_path, path)

            devices = filter_devices(_devices, vendor=vendor)
            recipe = punc.model.Recipe(
                name=name, devices=devices, ruleset=ruleset)
            collection = punc.collect.Collection(
                recipe,
                final_path,
                notch_client,
                command_timeout,
                collect_timeout)
            logging.debug('Adding %r', collection)
            collections.append(collection)

    return collections


def get_notch_client(agents):   
    # Setup notch client.
    try:
        nc = notch.client.Connection(agents)
    except notch.client.client.NoAgentsError, e:
        logging.error(str(e))
        return None
    else:
        return nc
