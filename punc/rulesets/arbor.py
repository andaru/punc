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

"""PUNC Arbor PeakFlow/TMS/Collector Platform device module."""


import re

import punc.model
import punc.parser


COMMENT = '# '


class ParseSysHardware(punc.parser.AddDropParser):
    """Parses "system hardware" output."""

    commented = True
    comment = COMMENT

    DROP_RE = (punc.parser.BLANK_LINE,
               re.compile(r'^Boot time:'),
               re.compile(r'^Load averages:'),
               )


class ParseSysConfiguration(punc.parser.AddDropParser):
    """Parses "system config show" output."""


class ArborRuleset(punc.model.Ruleset):
    """Arbor OS ruleset for PUNC."""

    name = 'arbor'

    cmd_sys_hardware = {'command': 'system hardware'}
    cmd_sys_config = {'command': 'system config show'}

    header = '#RANCID-CONTENT-TYPE: arbor\n#\n'

    def rules(self):
        return [
            punc.model.Rule([punc.model.Action('command',
                                               key=(0, 0),
                                               args=self.cmd_sys_hardware,
                                               parser=ParseSysHardware)]),
            punc.model.Rule([punc.model.Action('command',
                                               key=(1, 0),
                                               args=self.cmd_sys_config,
                                               parser=ParseSysConfiguration)]),
            ]
