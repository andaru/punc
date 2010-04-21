
import copy
import collections
import logging
import time
import traceback

import notch.client

import ruleset_factory


class InvalidCollectionError(Exception):
    """The collection defined was invalid."""


class Rule(object):

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
        self.rules = []
        self.path = path
        self._parse_config(config)

    def _parse_config(self, config):
        if not config.get('rules'):
            raise InvalidCollectionError(
                'Collection missing rules attribute. %r' % config)
        for rule in config.get('rules'):
            if not isinstance(rule, dict):
                continue
            self.rules.append(Rule(regexp=rule.get('regexp'),
                                   vendor=rule.get('vendor'),
                                   ruleset=rule.get('ruleset'),
                                   path=rule.get('path', self.path)))

    @property
    def results(self):
        """Get the results once all network requests are done."""
        return self._results
        
    def collect(self, nc):
        """Executes the collection with a Notch Client instance."""
        logging.info('Collection %s started', self.name)
        reqs = []
        start = time.time()
        for rule in self.rules:
            reg = rule.regexp
            devices = nc.devices_info(reg)
            notch_requests = self._get_requests(rule, *devices.keys())
            nc.exec_requests(notch_requests)
        
        end = time.time()
        logging.info('Send all requests for collection %s in %.2fs',
                     self.name, end-start)

    def _get_requests(self, rule, *devices):
        """Generates notch requests for the current rule and devices."""
        reqs = []
        try:
            ruleset = ruleset_factory.get_ruleset_with_name(rule.ruleset)
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
                                         callback_args=(rule, action))
                reqs.append(r)

        logging.debug('Generated %d request objects', len(reqs))
        return reqs

    def _notch_callback(self, r, *args, **kwargs):
        rule, action = args
        device_name = r.arguments.get('device_name')
        if r.error is not None:
            logging.debug('Got an error: %r', r.error)
            rule.errors.append((device_name, rule, action, str(r.error)))
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

            self._results[(rule, device_name, action.order)] = parsed_result

