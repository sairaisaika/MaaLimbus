"""The floor route table must order known nodes and refuse unknown ones."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maalimbus.route_plan import (
    KINDS,
    MODIFIERS,
    POLICY_VERSION,
    PolicyError,
    load_policy,
    plan_route,
    score_node,
)

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / 'assets' / 'resource' / 'base' / 'route-policy.json'


def shipped():
    return load_policy(SHIPPED)


def test_the_shipped_route_policy_scores_every_kind_and_no_other_key():
    policy = shipped()
    assert policy['version'] == POLICY_VERSION
    assert set(policy['weights']) == set(KINDS)
    assert set(policy['modifiers']) <= set(MODIFIERS)
    for kind in KINDS:
        assert score_node(kind, policy=policy) is not None


def test_a_written_policy_that_names_an_unknown_kind_is_rejected(tmp_path):
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps({'version': 1, 'weights': {'dragon': 1.0}}), encoding='utf-8')
    with pytest.raises(PolicyError):
        load_policy(bad)
    bad.write_text(json.dumps({'version': 9, 'weights': {'event': 1.0}}), encoding='utf-8')
    with pytest.raises(PolicyError):
        load_policy(bad)
    bad.write_text(json.dumps({'version': 1, 'weights': {'event': 1.0},
                              'modifiers': {'teleport': 1.0}}), encoding='utf-8')
    with pytest.raises(PolicyError):
        load_policy(bad)


def test_the_plan_takes_the_highest_scoring_candidate_and_carries_its_box():
    policy = shipped()
    plan = plan_route(
        [
            {'id': 'a', 'kind': 'empty', 'box': (10, 20, 30, 30)},
            {'id': 'b', 'kind': 'abnormality', 'box': (50, 60, 30, 30)},
            {'id': 'c', 'kind': 'event', 'box': (90, 100, 30, 30)},
        ],
        policy=policy,
    )
    assert plan['refused'] is None
    assert plan['target'] == 'b'
    assert plan['box'] == (50, 60, 30, 30)
    assert plan['reasons'] == sorted(plan['reasons']) == ['base_weight_abnormality']
    assert [entry['id'] for entry in plan['ranked']] == ['b', 'c', 'a']


def test_a_candidate_the_policy_cannot_score_is_skipped_and_an_empty_field_refuses():
    policy = shipped()
    plan = plan_route(
        [{'id': 'a', 'kind': 'unreadable'}, {'id': 'b', 'kind': 'regular'}],
        policy=policy,
    )
    assert plan['target'] == 'b' and plan['refused'] is None
    assert [entry['id'] for entry in plan['ranked']] == ['b']

    blind = plan_route([{'id': 'a', 'kind': 'unreadable'}], policy=policy)
    assert blind['target'] is None and blind['refused'] == 'route_kind_unknown'
    empty = plan_route([], policy=policy)
    assert empty['target'] is None and empty['refused'] == 'route_candidates_empty'


def test_wounds_push_an_elite_below_a_regular_fight():
    policy = shipped()
    healthy = plan_route([{'id': 'elite', 'kind': 'elite'}, {'id': 'trash', 'kind': 'regular'}],
                         policy=policy)
    assert healthy['target'] == 'elite'
    hurt = plan_route([{'id': 'elite', 'kind': 'elite'}, {'id': 'trash', 'kind': 'regular'}],
                      policy=policy, context={'wounded_ratio': 1.0})
    assert hurt['target'] == 'trash'
    assert hurt['ranked'][1]['reasons'] == ['base_weight_elite', 'wounded_penalty_2.000']


def test_a_pending_fusion_promotes_the_shop_over_a_fight():
    policy = shipped()
    plan = plan_route([{'id': 'shop', 'kind': 'shop'}, {'id': 'fight', 'kind': 'elite'}],
                      policy=policy, context={'fusion_pending': True})
    assert plan['target'] == 'shop'
    assert plan['reasons'] == ['base_weight_shop', 'fusion_shop_bonus_1.600']


def test_the_last_floor_pushes_the_boss_and_ties_break_on_input_order():
    policy = shipped()
    plan = plan_route([{'id': 'shop', 'kind': 'shop'}, {'id': 'boss', 'kind': 'boss'}],
                      policy=policy, context={'floor': 5, 'last_floor': True})
    assert plan['target'] == 'boss'
    assert plan['reasons'] == ['base_weight_boss', 'last_floor_boss_bonus_0.800']
    tie = plan_route([{'id': 'first', 'kind': 'event'}, {'id': 'second', 'kind': 'event'}],
                     policy=policy)
    assert tie['target'] == 'first'
    assert tie['score'] == tie['ranked'][1]['score']


def test_scoring_is_pure_and_stable_across_calls():
    policy = shipped()
    candidates = [{'id': 'a', 'kind': 'focused'}, {'id': 'b', 'kind': 'shop'}]
    context = {'wounded_ratio': 0.25, 'fusion_pending': True}
    first = plan_route(candidates, policy=policy, context=context)
    assert first == plan_route(candidates, policy=policy, context=dict(context))
    assert first['target'] == 'b'
    assert score_node('shop', policy=policy, context=context) == score_node(
        'shop', policy=policy, context=dict(context))
