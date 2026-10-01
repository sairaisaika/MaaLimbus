"""Saved-team labels stay independent of identity art and preset numbers."""
import re
from .vision import find


def team_pattern(team, locale='en'):
    if team.name:
        return r'^\s*' + re.escape(team.name).replace(r'\ ', r'\s*') + r'\s*$'
    prefix = r'TEAMS?' if locale == 'en' else r'(?:チーム|TEAMS?)'
    return rf'^\s*{prefix}\s*#?\s*{team.slot}\s*$'


def team_row(records, team, locale, size):
    matches = find(records, team_pattern(team, locale), (.04, .28, .19, .80), size, .8)
    return matches[0] if len(matches) == 1 else None


def team_header(records, team, locale, size):
    matches = find(records, team_pattern(team, locale), (.16, .07, .40, .18), size, .8)
    return matches[0] if len(matches) == 1 else None
