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


COMMENT = '# '

ERRORS = (
    re.compile(
        r'not found in path'),
    re.compile(
        r'Next possible completions'),
    re.compile(
        r'Available commands'),
    )


class ParseConfiguration(punc.parser.AddDropParser):
    """Parses "show configuration" output."""

    DROP_RE = (punc.parser.BLANK_LINE,
               re.compile(r'^Command: show configuration'),
               re.compile(r'^Using [0-9]+ out of'),
               )
    IGNORE_RE = ERRORS


class NortelEsuRuleset(punc.model.Ruleset):
    """Nortel ESU ruleset for PUNC."""

    name = 'nortel_esu'

    cmd_show_config = {'command': 'show configuration'}

    header = '#RANCID-CONTENT-TYPE: nortel_esu\n#\n'

    def rules(self):
        return [
            punc.model.Rule([punc.model.Action('command',
                                               key=(0, 0),
                                               args=self.cmd_show_config,
                                               parser=ParseConfiguration)]),
            ]
