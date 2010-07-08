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

"""PUNC NOS (e.g., Hitachi/DASAN EOLT) device ruleset."""


import re

import punc.model
import parser

COMMENT = '! '


ERRORS = (
    re.compile(
        "\\%\\ Invalid\\ input\\ detected\\ at\\ \\'\\^\\'\\ marker\\."),
    )


class ParseShowSystem(punc.parser.AddDropParser):
    """Parse the NOS "show system" output."""

    commented = True
    comment = COMMENT

    DROP_RE = (punc.parser.BLANK_LINE,
               )

    ERRORS_RE = ERRORS
    

class ParseConfiguration(punc.parser.AddDropParser):
    """Parse the NOS "show running-config" output."""

    DROP_RE = (punc.parser.BLANK_LINE,
               re.compile(r'^Building configuration\.'),
               re.compile(r'^Current configuration'),
               re.compile(r'Last configuration change at '),
               re.compile(r'NVRAM config last updated at '),
               re.compile(r'^ntp clock-period [0-9]+'),
               re.compile('Using [0-9].*'),
               )
    ERROR_RE = ERRORS


class NosRuleset(punc.model.Ruleset):
    """DASAN NOS rule set for PUNC."""

    name = 'nos'

    cmd_show_system = {'command': 'show system'}
    cmd_show_running = {'command': 'show running-config'}

    header = '!RANCID-CONTENT-TYPE: nos\n!\n'

    def rules(self):
        return [
            punc.model.Rule([punc.model.Action('command',
                                               key=(0, 0),
                                               args=self.cmd_show_system,
                                               parser=ParseShowSystem)]),
            punc.model.Rule([punc.model.Action('command',
                                               key=(1, 0),
                                               args=self.cmd_show_running,
                                               parser=ParseConfiguration)]),
            ]
