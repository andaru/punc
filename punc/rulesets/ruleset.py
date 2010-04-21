
import collections

Action = collections.namedtuple('Action',
                                'notch_method args order parser parser_args')


class RuleSet(object):

    actions = []

    # A string, the RANCID-CONTENT-TYPE header.
    header = ''

    def __init__(self):
        # Actions is a sequence of Action namedtuples.
        #
        # Example:
        #
        # _show_version = {'command': 'show version'}
        # _show_running = {'command': 'show running-config'}
        #
        # actions = [
        #     ruleset.Action(notch_method='command', args=_show_version,
        #                    order='001', parser=self.parse_show_version,
        #                    parser_args={}),
        #     ruleset.Action(notch_method='command', args=_show_running,
        #                    order='002', parser=self.parse_configuration,
        #                    parser_args={}),
        #     ]
        self.actions = []
