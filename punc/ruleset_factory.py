from rulesets import cisco
from rulesets import telco


rulesets = {'cisco': cisco.IosRuleSet,
            'telco': telco.TelcoRuleSet,
            }


def get_ruleset_with_name(name):
    ruleset = rulesets.get(name)
    if ruleset is not None:
        return ruleset()
    else:
        raise KeyError(name)

