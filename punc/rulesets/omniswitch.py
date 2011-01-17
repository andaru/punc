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

"""PUNC Alcatel-Lucent Omniswitch device ruleset."""


import punc.model
import punc.parser


COMMENT = '! '


class ParseConfiguration(punc.parser.AddDropParser):
    """Parses "show configuration snapshot" output."""

    # Default configuration is fine for this command and device.


class ParseShowHardwareInfo(punc.parser.AddDropParser):
    """Parses "show hardware info" output."""

    commented = True
    comment = COMMENT

    DROP_RE = (punc.parser.BLANK_LINE,
               )
    

class OmniswitchRuleset(punc.model.Ruleset):
    """ALU Omniswitch ruleset for PUNC."""

    name = 'omniswitch'

    cmd_show_hardware = {'command': 'show hardware info'}
    cmd_show_running = {'command': 'show configuration snapshot'}

    header = '!RANCID-CONTENT-TYPE: omniswitch\n!\n'

    def rules(self):
        return [
            punc.model.Rule([punc.model.Action('command',
                                               key=(0, 0),
                                               args=self.cmd_show_hardware,
                                               parser=ParseShowHardwareInfo)]),
            punc.model.Rule([punc.model.Action('command',
                                               key=(1, 0),
                                               args=self.cmd_show_running,
                                               parser=ParseConfiguration)]),
            ]
