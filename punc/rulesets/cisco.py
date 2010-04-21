import re

import ruleset
import parser

COMMENT = '! '

class ParseShowVersion(parser.AddDropParser):

    commented = True
    comment = COMMENT

    DROP_RE = (parser.BLANK_LINE,
               )
    INC_RE = (re.compile('version', re.I),
              re.compile('Using [0-9].*'),
              )


class ParseConfiguration(parser.AddDropParser):
    """Empty parser."""

    DROP_RE = (parser.BLANK_LINE,
              re.compile('Using [0-9].*'),
               )


class IosRuleSet(ruleset.RuleSet):

    _show_version = {'command': 'show version'}
    _show_running = {'command': 'show startup'}

    header = '!RANCID-CONTENT-TYPE: cisco\n!'

    def __init__(self):
        self.actions = [
            ruleset.Action(notch_method='command', args=self._show_version,
                           order='001', parser=ParseShowVersion,
                           parser_args={}),
            ruleset.Action(notch_method='command', args=self._show_running,
                           order='002', parser=ParseConfiguration,
                           parser_args={}),
            ]


