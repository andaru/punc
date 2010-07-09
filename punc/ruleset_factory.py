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

"""PUNC's ruleset factory."""


import punc.rulesets.adva_fsp
import punc.rulesets.arbor
import punc.rulesets.cisco
import punc.rulesets.dasan_nos
import punc.rulesets.telco
import punc.rulesets.timetra


RULESETS = (punc.rulesets.adva_fsp.AdvaFspRuleset,
            punc.rulesets.arbor.ArborRuleset,
            punc.rulesets.cisco.IosRuleset,
            punc.rulesets.dasan_nos.NosRuleset,
            punc.rulesets.telco.TelcoRuleset,
            punc.rulesets.timetra.TimetraRuleset,
            )


rulesets = {}
for ruleset in RULESETS:
    rulesets[ruleset.name] = ruleset

    
def get_ruleset(name):
    """Returns a ruleset object.

    Args:
      name: A string, the ruleset name, e.g., 'cisco', 'nos' to, retrieve.

    Returns:
      A model.Ruleset subclass instance, the ruleset.

    Raises:
      KeyError: The ruleset name was unknown.
    """
    return rulesets[name]()
