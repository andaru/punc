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

"""Alcatel/Timetra TimOS collection rules."""


import re

import punc.model

import punc.parser


COMMENT = '# '


class ParseShowVersion(punc.parser.AddDropParser):

    commented = True
    comment = COMMENT

    DROP_RE = (punc.parser.BLANK_LINE,
               )


class ParseConfiguration(punc.parser.AddDropParser):
    """Configuration parser."""

    DROP_RE = (punc.parser.BLANK_LINE,
               re.compile(r'^# Built on '),
               re.compile(r'^# Generated [A-Z]'),
               re.compile(r'^# All rights reserved. All use subject to '),
               re.compile(r'^# TiMOS-'),
               re.compile(r'^# Finished [A-Z]'),
               )


class TimetraRuleset(punc.model.Ruleset):

    name = 'timetra'

    cmd_show_version = {'command': 'show version'}
    cmd_show_running = {'command': 'admin display-config'}

    header = '# RANCID-CONTENT-TYPE: timetra\n#\n'

    def rules(self):
        return [
            punc.model.Rule([punc.model.Action('command',
                                               key=(0, 0),
                                               args=self.cmd_show_version,
                                               parser=ParseShowVersion)]),
            punc.model.Rule([punc.model.Action('command',
                                               key=(1, 0),
                                               args=self.cmd_show_running,
                                               parser=ParseConfiguration)]),
            ]

