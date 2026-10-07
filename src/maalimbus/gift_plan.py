"""Which starting E.G.O Gift to take, per team attribute.

The player's rule: a run can either always take one fixed gift, or let the team's
attribute (its keyword) decide which gift to look for. Both are the same lookup —
a list of names per keyword, with ``default`` underneath — so a fixed gift is just
a plan whose every attribute points at the same name.

Live shape of the file: ``assets/resource/base/gift-plan.json``.
"""
import json

NAME = 'gift-plan.json'


def load(path):
    """Read a gift plan; raise on a file that cannot answer the lookup."""
    with open(path, encoding='utf-8') as handle:
        plan = json.load(handle)
    return validate(plan)


def validate(plan):
    """Check the plan's shape and return it, so a bad file fails loudly."""
    if not isinstance(plan, dict):
        raise ValueError('%s must hold an object' % NAME)
    default = plan.get('default', [])
    teams = plan.get('teams', {})
    if not isinstance(default, list) or not isinstance(teams, dict):
        raise ValueError('%s needs a "default" list and a "teams" object' % NAME)
    for key, names in list(teams.items()) + [('default', default)]:
        if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
            raise ValueError('%s: %r must be a list of gift names' % (NAME, key))
    return plan


def wanted(plan, keyword, *, fallback=('Wound Clerid',)):
    """The gift names to try, best first, for the team's ``keyword``.

    An attribute with no list of its own falls back to ``default``, and a plan with
    neither falls back to the names the player already confirmed by hand.
    """
    key = (keyword or '').strip().lower()
    teams = {str(name).strip().lower(): list(names)
             for name, names in (plan or {}).get('teams', {}).items()}
    if key and teams.get(key):
        return teams[key]
    default = list((plan or {}).get('default') or [])
    return default or list(fallback)
