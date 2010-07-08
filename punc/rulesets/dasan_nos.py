import re

import ruleset
import parser

COMMENT = '! '


ERRORS = (
    re.compile(
        "\\%\\ Invalid\\ input\\ detected\\ at\\ \\'\\^\\'\\ marker\\."),
    )


class ParseShowSystem(parser.AddDropParser):
    """Parse the NOS "show system" output."""

    commented = True
    comment = COMMENT

    DROP_RE = (parser.BLANK_LINE,
               )

    ERRORS_RE = ERRORS
    

class ParseConfiguration(parser.AddDropParser):
    """Parse the NOS "show running-config" output."""

    DROP_RE = (parser.BLANK_LINE,
               re.compile(r'^Building configuration\.'),
               re.compile(r'^Current configuration'),
               re.compile(r'Last configuration change at '),
               re.compile(r'NVRAM config last updated at '),
               re.compile(r'^ntp clock-period [0-9]+'),
               re.compile('Using [0-9].*'),
               )
    ERROR_RE = ERRORS


class NosRuleSet(ruleset.RuleSet):

    _show_system = {'command': 'show system'}
    _show_running = {'command': 'show running-config'}

    header = '!RANCID-CONTENT-TYPE: nos\n!'

    def __init__(self):
        self.actions = [
            ruleset.Action(notch_method='command', args=self._show_system,
                           order='001', parser=ParseShowSystem,
                           parser_args={}),
            ruleset.Action(notch_method='command', args=self._show_running,
                           order='002', parser=ParseConfiguration,
                           parser_args={}),
            ]
