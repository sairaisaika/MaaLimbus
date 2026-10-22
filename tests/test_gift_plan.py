"""The starting-gift plan: one fixed gift, or one gift per team attribute."""
import json
from pathlib import Path

import pytest

from maalimbus import gift_plan
from maalimbus.gift_plan import wanted

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


def test_a_multi_system_team_gets_both_systems_best_first():
    """The charge+tremor team must not be served one system and silently lose the other."""
    plan = {'teams': {'charge': ['Charged Battery'], 'tremor': ['Tremor Pipe', 'Tremor Rod']}}
    assert wanted(plan, 'charge+tremor') == ['Charged Battery', 'Tremor Pipe', 'Tremor Rod']
    assert wanted(plan, ('charge', 'tremor')) == ['Charged Battery', 'Tremor Pipe', 'Tremor Rod']
    # A single keyword keeps its old meaning exactly.
    assert wanted(plan, 'tremor') == ['Tremor Pipe', 'Tremor Rod']


def test_a_duplicate_gift_across_systems_is_offered_once():
    plan = {'teams': {'charge': ['Shared'], 'tremor': ['Shared', 'Only Tremor']}}
    assert wanted(plan, 'charge+tremor') == ['Shared', 'Only Tremor']


def test_an_unknown_system_falls_through_to_the_default():
    plan = {'teams': {'charge': ['Charged Battery']}, 'default': ['Fallback']}
    assert wanted(plan, 'poise') == ['Fallback']
