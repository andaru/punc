import re

import parser
import ruleset


class AdvaSetupBackupParser(parser.AddDropParser):
    """Sets up the configuration backup on the Adva FSP."""

    IGNORE_RE = (re.compile(r'^backup completed successfully'),
                 )
    
    ERROR_RE = (re.compile(r'.*aborting'),
                )


class AdvaFspRuleSet(ruleset.RuleSet):

    _get_config = {'source': '/rdisk/configuration.img.DBS'}
    _setup_backup = {'command': 'fsp_update.f7 backup configuration.img'}

    def __init__(self):
        self.actions = [
            ruleset.Action(notch_method='command',
                           args=self._setup_backup,
                           order='000', parser=AdvaSetupBackupParser),
            ruleset.Action(notch_method='get_config',
                           args=self._get_config,
                           order='001', parser=None,
                           output_file_suffix='-configuration.img.DBS',
                           binary_result=True),
            ]
