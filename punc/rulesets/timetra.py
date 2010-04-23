import re

import ruleset
import parser

COMMENT = '# '


class ParseShowVersion(parser.AddDropParser):

    commented = True
    comment = COMMENT

    DROP_RE = (parser.BLANK_LINE,
               )


class ParseConfiguration(parser.AddDropParser):
    """Configuration parser."""

    DROP_RE = (parser.BLANK_LINE,
               re.compile(r'Built on .+ '),
               re.compile(r'Generated .+ '),
               re.compile(r'All rights reserved. All use subject to .*'),
               re.compile(r'TiMOS-'),
               )


class TimetraRuleSet(ruleset.RuleSet):

    _show_version = {'command': 'show version'}
    _show_running = {'command': 'admin display-config'}

    header = '# RANCID-CONTENT-TYPE: timetra\n# '

    def __init__(self):
        self.actions = [
            ruleset.Action(notch_method='command', args=self._show_version,
                           order='001', parser=ParseShowVersion,
                           parser_args={}),
            ruleset.Action(notch_method='command', args=self._show_running,
                           order='002', parser=ParseConfiguration,
                           parser_args={}),
            ]

