"""The starting-gift plan: one fixed gift, or one gift per team attribute."""
import json
from pathlib import Path

import pytest

from maalimbus import gift_plan

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / 'assets' / 'resource' / 'base' / 'gift-plan.json'


def test_the_shipped_plan_names_the_bleed_gifts_the_player_confirmed():
    plan = gift_plan.load(SHIPPED)
    assert gift_plan.wanted(plan, 'bleed') == ['Wound Clerid',
                                               'Little and To-be-Naughty Plushie']
    # The keyword is matched case-insensitively, and other attributes fall back.
    assert gift_plan.wanted(plan, 'Bleed') == gift_plan.wanted(plan, 'bleed')
    assert gift_plan.wanted(plan, 'burn') == plan['default']
    assert gift_plan.wanted(plan, '') == plan['default']


def test_a_fixed_gift_is_a_plan_where_every_attribute_holds_the_same_name():
    fixed = {'default': ['Wound Clerid'],
             'teams': {'bleed': ['Wound Clerid'], 'burn': ['Wound Clerid']}}
    assert gift_plan.wanted(fixed, 'burn') == ['Wound Clerid']
    assert gift_plan.wanted(fixed, 'slash') == ['Wound Clerid']


def test_an_empty_plan_falls_back_to_what_the_player_already_named():
    assert gift_plan.wanted({}, 'bleed') == ['Wound Clerid']
    assert gift_plan.wanted({}, '') == ['Wound Clerid']


def test_a_malformed_plan_fails_loudly(tmp_path):
    bad = tmp_path / 'gift-plan.json'
    bad.write_text(json.dumps({'default': 'Wound Clerid'}), encoding='utf-8')
    with pytest.raises(ValueError):
        gift_plan.load(bad)
    bad.write_text(json.dumps({'default': ['ok'], 'teams': {'bleed': [7]}}),
                   encoding='utf-8')
    with pytest.raises(ValueError):
        gift_plan.load(bad)
    bad.write_text(json.dumps([]), encoding='utf-8')
    with pytest.raises(ValueError):
        gift_plan.load(bad)
