
class Action(object):
    """A Notch Action within a RuleSet."""

    def __init__(self, notch_method=None, args=None, order=None,
                 parser=None, parser_args={}, output_file_suffix=None,
                 binary_result=False):
        self.notch_method = notch_method
        self.args = args
        self.order = order
        self.parser = parser
        self.parser_args = parser_args
        self.output_file_suffix = output_file_suffix
        self.binary_result = binary_result


class RuleSet(object):

    actions = []

    # A string, the RANCID-CONTENT-TYPE header.
    # Leave empty to avoid writing such a header line.
    header = ''

    def __init__(self):
        # Actions is a sequence of Action namedtuples.
        #
        # Example:
        #
        # _show_version = {'command': 'show version'}
        # _show_running = {'command': 'show running-config'}
        #
        # self.actions = [
        #     ruleset.Action(notch_method='command', args=_show_version,
        #                    order='001', parser=self.parse_show_version,
        #                    parser_args={}),
        #     ruleset.Action(notch_method='command', args=_show_running,
        #                    order='002', parser=self.parse_configuration,
        #                    parser_args={}),
        #     ]
        self.actions = []
