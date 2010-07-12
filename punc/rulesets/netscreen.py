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

"""PUNC Netscreen OS device ruleset."""


import re

import punc.model
import punc.parser


COMMENT = '# '

ERRORS = (
    re.compile(
        "\\%\\ Invalid\\ input\\ detected\\ at\\ \\'\\^\\'\\ marker\\."),
    )


class ParseGetSystem(punc.parser.AddDropParser):
    """Parses "get system" output."""

    commented = True
    comment = COMMENT

    DROP_RE = (punc.parser.BLANK_LINE,
               )
    INC_RE = (re.compile('version', re.I),
              re.compile('Using [0-9].*'),
              )
    ERROR_RE = ERRORS


class ParseConfiguration(punc.parser.AddDropParser):
    """Parses "get config" output."""

    DROP_RE = (punc.parser.BLANK_LINE,
               re.compile(r'^Total Config size '),
               )
    # DROP_RE = (punc.parser.BLANK_LINE,
    #            re.compile(r'^Building configuration\.'),
    #            re.compile(r'^Current configuration'),
    #            re.compile(r'Last configuration change at '),
    #            re.compile(r'NVRAM config last updated at '),
    #            re.compile(r'^ntp clock-period [0-9]+'),
    #            re.compile('Using [0-9].*'),
    #            )
    ERROR_RE = ERRORS


class NetscreenRuleset(punc.model.Ruleset):
    """Netscreen ScreenOS ruleset for PUNC."""

    name = 'netscreen'

    cmd_get_system = {'command': 'get system'}
    cmd_get_config = {'command': 'get config'}

    header = '#RANCID-CONTENT-TYPE: netscreen\n#\n'

    def rules(self):
        return [
            # punc.model.Rule([punc.model.Action('command',
            #                                    key=(0, 0),
            #                                    args=self.cmd_get_system,
            #                                    parser=ParseGetSystem)]),
            punc.model.Rule([punc.model.Action('command',
                                               key=(1, 0),
                                               args=self.cmd_get_config,
                                               parser=ParseConfiguration)]),
            ]
