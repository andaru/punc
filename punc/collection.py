
import copy
import collections
import logging
import re
import time
import traceback

import notch.client

import ruleset_factory


class InvalidCollectionError(Exception):
    """The collection defined was invalid."""


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

    def __init__(self, name, config, path='./punc-repo'):
        """Initialiser.

        Args:
          name: A string, the collection name.
          config: A dict, the collection config rooted at
            the name of the collection (with a 'recipes' sub-element).
          path: The base path to use for this collection.
        """
        self.name = name
        self._devices = {}
        self._errors = []
        self._results = {}
        self.recipes = []
        self.path = path
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
            
    def collect(self, nc, filter=None):
        """Executes the collection with a Notch Client instance."""
        logging.info('[%s] started', self.name)
        reqs = []
        start = time.time()
        self._devices = {}
        for recipe in self.recipes:
            reg = recipe.regexp
            devices = nc.devices_info(reg)
            self._devices.update(devices)
            notch_requests = self._get_requests(recipe, filter,
                                                *devices.keys())
            nc.exec_requests(notch_requests)
        
        end = time.time()
        logging.info('[%s] requests sent in %.2fs',
                     self.name, end-start)

    def _get_requests(self, recipe, filter, *devices):
        """Generates notch requests for the current recipe and devices."""
        reqs = []
        try:
            ruleset = ruleset_factory.get_ruleset_with_name(recipe.ruleset)
        except KeyError, exc:
            logging.debug('[%s] No ruleset for device type %s', self.name, exc)
            return reqs

        reqs = []
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
                if device_vendor != recipe.vendor:
                    continue
                args = copy.copy(action.args)
                args['device_name'] = device
                r = notch.client.Request(action.notch_method, args,
                                         callback=self._notch_callback,
                                         callback_args=(recipe, action))
                reqs.append(r)

        logging.debug('[%s] %d requests for %r',
                      self.name, len(reqs), recipe)
        return reqs

    def _notch_callback(self, r, *args, **kwargs):
        recipe, action = args
        device_name = r.arguments.get('device_name')
        if r.error is not None:
            if r.error.args[1].startswith('ERROR '):
                error_msg = r.error.args[1].split(':', 1)[1].strip()
            else:
                error_msg = str(r.error)
            logging.error('[%s] %s: %s: %s',
                          self.name, device_name, r.error.args[0], error_msg)
            recipe.errors.append((device_name, action, error_msg))
        else:
            result = r.result
            try:
                parser = action.parser(result)
                parsed_result = parser.Parse()
                # TODO(afort):
                # Detect a sequence response being a sequence of tuples of
                # (device_name, action.order, [lines])
            except Exception, e:
                logging.error('Produced an error during parsing. Traceback:')
                logging.error(traceback.format_exc())
                logging.error('Using unparsed data in result.')
                parsed_result = result

            self._results[(recipe, device_name, action.order)] = parsed_result

