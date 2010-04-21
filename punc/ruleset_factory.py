
from rulesets import cisco


rulesets = {'cisco': cisco.IosRuleSet,
            }


def get_ruleset_with_name(name):
    ruleset = rulesets.get(name)
    if ruleset is not None:
        return ruleset()
    else:
        raise KeyError(name)

