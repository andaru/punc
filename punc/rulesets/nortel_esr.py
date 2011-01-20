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

"""Nortel ESR device ruleset."""


import re

import punc.model
import punc.parser


COMMENT = '! '

ERRORS = (
    re.compile(
        "not\\ found\\ in\\ path\\ "),
    )


class ParseConfiguration(punc.parser.AddDropParser):
    """Parses "show config" output."""

    DROP_RE = (punc.parser.BLANK_LINE,
               re.compile(r'^Preparing to Display Configuration\.\.'),
               re.compile(r'^# (MON|TUE|WED|THU|FRI|SAT|SUN) [A-Z]+'),
               )
    SUBST_RE = ((re.compile(r'(^# Slot.+) CF=.+$'), r'\1'),
                )
    ERROR_RE = ERRORS


class NortelEsrRuleset(punc.model.Ruleset):
    """Nortel ESR ruleset for PUNC."""

    name = 'nortel_esr'

    cmd_show_config = {'command': 'show config'}

    header = '#RANCID-CONTENT-TYPE: nortel_esr\n#\n'

    def rules(self):
        return [
            punc.model.Rule([punc.model.Action('command',
                                               key=(0, 0),
                                               args=self.cmd_show_config,
                                               parser=ParseConfiguration)]),
            ]
