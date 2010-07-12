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

"""PUNC Adva FSP3000 device ruleset."""

import re

import punc.model
import punc.parser


class AdvaSetupBackupParser(punc.parser.AddDropParser):
    """Sets up the configuration backup on the Adva FSP."""

    IGNORE_RE = (re.compile(r'^backup completed successfully'),
                 )
    
    ERROR_RE = (re.compile(r'.*aborting'),
                )


binary_config_target = punc.model.Target(file_suffix='_configuration.img.DBS',
                                         target_mode='b')


class AdvaFspRuleset(punc.model.Ruleset):
    """Adva FSP3000 (DWDM Mux) ruleset for PUNC."""

    name = 'adva_fsp'

    cmd_get_config = {'source': '/rdisk/configuration.img.DBS'}
    cmd_setup_backup = {'command': 'fsp_update.f7 backup configuration.img'}

    def rules(self):
        return [
            punc.model.Rule([punc.model.Action('command',
                                               key=(0, 0),
                                               args=self.cmd_setup_backup,
                                               parser=AdvaSetupBackupParser),
                             punc.model.Action('get_config',
                                               key=(0, 1),
                                               args=self.cmd_get_config,
                                               parser=None,
                                               target=binary_config_target),
                             ]),
            ]
