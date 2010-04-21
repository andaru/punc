
import copy
import collections
import logging
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

    def __init__(self, name, config, path='./'):
        self.name = name
        self._devices = {}
        self._errors = []
        self._results = {}
        self.recipes = []
        self.path = path
        self._parse_config(config)

    def _parse_config(self, config):
        if not config.get('recipes'):
            raise InvalidCollectionError(
                'Collection missing recipes attribute. %r' % config)
        for recipe in config.get('recipes'):
            if not isinstance(recipe, dict):
                continue
            self.recipes.append(Recipe(regexp=recipe.get('regexp'),
                                   vendor=recipe.get('vendor'),
                                   ruleset=recipe.get('ruleset'),
                                   path=recipe.get('path', self.path)))

    @property
    def results(self):
        """Get the results once all network requests are done."""
        return self._results
        
    def collect(self, nc):
        """Executes the collection with a Notch Client instance."""
        logging.info('Collection %s started', self.name)
        reqs = []
        start = time.time()
        for recipe in self.recipes:
            reg = recipe.regexp
            devices = nc.devices_info(reg)
            notch_requests = self._get_requests(recipe, *devices.keys())
            nc.exec_requests(notch_requests)
        
        end = time.time()
        logging.info('Send all requests for collection %s in %.2fs',
                     self.name, end-start)

    def _get_requests(self, recipe, *devices):
        """Generates notch requests for the current recipe and devices."""
        reqs = []
        try:
            ruleset = ruleset_factory.get_ruleset_with_name(recipe.ruleset)
        except KeyError, exc:
            logging.debug('No ruleset for device type %s', exc)
            return reqs

        reqs = []
        for action in ruleset.actions:

            for device in devices:
                args = copy.copy(action.args)
                args['device_name'] = device
                r = notch.client.Request(action.notch_method, args,
                                         callback=self._notch_callback,
                                         callback_args=(recipe, action))
                reqs.append(r)

        logging.debug('Generated %d request objects', len(reqs))
        return reqs

    def _notch_callback(self, r, *args, **kwargs):
        recipe, action = args
        device_name = r.arguments.get('device_name')
        if r.error is not None:
            logging.debug('Got an error: %r', r.error)
            recipe.errors.append((device_name, action, str(r.error)))
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

