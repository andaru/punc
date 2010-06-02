from rulesets import cisco
from rulesets import dasan_nos
from rulesets import telco
from rulesets import timetra


rulesets = {'cisco': cisco.IosRuleSet,
            'nos': dasan_nos.NosRuleSet,
            'telco': telco.TelcoRuleSet,
            'timetra': timetra.TimetraRuleSet,
            }


def get_ruleset_with_name(name):
    ruleset = rulesets.get(name)
    if ruleset is not None:
        return ruleset()
    else:
        raise KeyError(name)

