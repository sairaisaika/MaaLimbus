"""Focused tests for the boss-adjacent shop settings resolver.

This resolver is settings only: it must accept the player's own refresh limit and coin
reserve, never lower the reserve floor, and never take a learning decision.
"""
from __future__ import annotations

import json

import pytest

from maalimbus.shop_settings import (
    FIELDS,
    LEARNED_OBEYS,
    POLICIES,
    REASONS,
    REFRESH_CAP,
    REFRESH_CHOICES,
    REFRESH_RANGE,
    RESERVE_CAP,
    RESERVE_CHOICES,
    RESERVE_RANGE,
    RUNTIME_DEFAULTS,
    collect,
    resolve_shop_settings,
    shop_settings_protocol,
)


def card(saved=None, overrides=None):
    return resolve_shop_settings(saved, overrides)


def reasons(result):
    return list(result['reasons'])


# ------------------------------------------------------------------ defaults and saved

def test_an_untouched_install_resolves_to_the_runtime_defaults():
    result = card()
    assert (result['shop_policy'], result['shop_refreshes'],
            result['shop_reserve_coins']) == (RUNTIME_DEFAULTS['shop_policy'],
                                              RUNTIME_DEFAULTS['shop_refreshes'],
                                              RUNTIME_DEFAULTS['shop_reserve_coins'])
    assert (result['shop_policy'], result['shop_refreshes'],
            result['shop_reserve_coins']) == ('manual', 2, 0)
    assert reasons(result) == ['runtime_default_used'] * 3
    assert result['state_written'] is False


def test_a_stored_choice_is_kept_when_nothing_overrides_it():
    result = card({'shop_policy': 'learned', 'shop_refreshes': 3, 'shop_reserve_coins': 200})
    assert (result['shop_policy'], result['shop_refreshes'],
            result['shop_reserve_coins']) == ('learned', 3, 200)
    assert reasons(result) == ['policy_saved', 'refresh_saved', 'reserve_saved']


def test_saved_fields_keep_their_stored_values_per_field():
    result = card({'shop_policy': 'manual', 'shop_reserve_coins': 500})
    assert result['shop_refreshes'] == RUNTIME_DEFAULTS['shop_refreshes']
    assert result['shop_reserve_coins'] == 500
    assert 'runtime_default_used' in reasons(result)


def test_an_explicit_saved_value_is_recorded_as_a_kept_choice_not_as_a_default():
    result = card({'shop_policy': 'saved', 'shop_refreshes': 'saved'},
                  {'shop_policy': 'saved', 'shop_refreshes': 'saved'})
    assert 'kept_launch_choice' in reasons(result)
    # The explicit "saved" is a kept choice, so the policy is not reported as a silent default.
    assert reasons(result).count('runtime_default_used') == 2
    assert (result['shop_policy'], result['shop_refreshes']) == ('manual',
                                                                RUNTIME_DEFAULTS['shop_refreshes'])


def test_overrides_win_over_the_stored_choice():
    result = card({'shop_policy': 'manual', 'shop_refreshes': 1, 'shop_reserve_coins': 100},
                  {'shop_policy': 'learned', 'shop_refreshes': 5, 'shop_reserve_coins': 300})
    assert (result['shop_policy'], result['shop_refreshes'],
            result['shop_reserve_coins']) == ('learned', 5, 300)
    assert reasons(result) == ['policy_learned', 'refresh_manual', 'reserve_manual',
                               'reserve_floor_raised']
    assert (result['policy_source'], result['refresh_source'],
            result['reserve_source']) == ('manual', 'manual', 'manual')


def test_an_explicit_saved_leaves_the_stored_choice_alone():
    result = card({'shop_policy': 'learned', 'shop_refreshes': 3, 'shop_reserve_coins': 200},
                  {'shop_policy': 'saved', 'shop_refreshes': 'saved',
                   'shop_reserve_coins': 'saved'})
    assert (result['shop_policy'], result['shop_refreshes'],
            result['shop_reserve_coins']) == ('learned', 3, 200)


@pytest.mark.parametrize('mode', POLICIES)
def test_every_declared_mode_resolves(mode):
    result = card(None, {'shop_policy': mode})
    assert result['shop_policy'] == ('manual' if mode == 'saved' else mode)

def test_modes_are_read_case_insensitively():
    assert card(None, {'shop_policy': ' LEARNED '})['shop_policy'] == 'learned'


# --------------------------------------------------------- learned obeys, never decides

def test_learned_keeps_both_hard_settings_exactly_as_given():
    result = card(None, {'shop_policy': 'learned', 'shop_refreshes': 5,
                         'shop_reserve_coins': 500})
    assert (result['shop_refreshes'], result['shop_reserve_coins']) == (5, 500)
    assert result['learned_applied'] is False
    assert result['model_trained'] is False
    assert 'learned_applied' not in result or result['learned_applied'] is False


def test_learned_never_lowers_the_coin_reserve_floor():
    result = card({'shop_reserve_coins': 300}, {'shop_policy': 'learned',
                                                'shop_reserve_coins': 100})
    assert result['shop_reserve_coins'] == 300
    assert 'reserve_floor_kept' in reasons(result)
    assert reasons(result)[-1] != 'reserve_floor_raised'


def test_learned_may_raise_the_coin_reserve_and_says_so():
    result = card({'shop_reserve_coins': 100}, {'shop_policy': 'learned',
                                                'shop_reserve_coins': 300})
    assert result['shop_reserve_coins'] == 300
    assert 'reserve_floor_raised' in reasons(result)


def test_learned_declares_the_settings_it_may_obey_and_no_model():
    result = card(None, {'shop_policy': 'learned'})
    assert result['learned_obeys'] == list(LEARNED_OBEYS)
    assert result['learned_applied'] is False
    assert 'trained purchase model' in result['limitation']
    assert result['ranges']['shop_refreshes'] == [0, 5]
    assert result['ranges']['shop_reserve_coins'] == [0, 500]


def test_the_hard_caps_are_reported_and_never_change_a_value():
    result = card(None, {'shop_refreshes': 5, 'shop_reserve_coins': 500})
    assert result['caps'] == {'shop_refreshes': REFRESH_CAP, 'shop_reserve_coins': RESERVE_CAP}
    assert (result['shop_refreshes'], result['shop_reserve_coins']) == (5, 500)


def test_nothing_the_resolver_returns_is_a_learning_result():
    result = card(None, {'shop_policy': 'learned'})
    assert result['learned_applied'] is False
    assert result['game_controller'] is False and result['input_sent'] is False
    assert 'evidence' not in result and 'learned' not in result


# --------------------------------------------------------------------- strict integers

def test_the_cap_boundaries_are_accepted():
    for value, field in ((0, 'shop_refreshes'), (5, 'shop_refreshes'),
                         (0, 'shop_reserve_coins'), (500, 'shop_reserve_coins')):
        assert card(None, {field: value})[field] == value


def test_any_integer_inside_the_range_is_accepted_not_only_the_drop_down_choices():
    assert card(None, {'shop_refreshes': 4})['shop_refreshes'] == 4
    assert card(None, {'shop_reserve_coins': 250})['shop_reserve_coins'] == 250
    assert 4 not in REFRESH_CHOICES and 250 not in RESERVE_CHOICES


@pytest.mark.parametrize('value, message', [
    ('3', 'must be the string "saved" or an integer'),
    ('05', 'must be the string "saved" or an integer'),
    ('', 'must be the string "saved" or an integer'),
    (True, 'must be the string "saved" or an integer'),
    (False, 'must be the string "saved" or an integer'),
    (2.0, 'must be the string "saved" or an integer'),
    (2.5, 'must be the string "saved" or an integer'),
    ('five', 'must be the string "saved" or an integer'),
    ([2], 'must be the string "saved" or an integer'),
    (6, 'must be an integer 0..5'),
    (-1, 'must be an integer 0..5'),
])
def test_refresh_refuses_a_non_integer_or_an_out_of_range_value(value, message):
    with pytest.raises(ValueError) as excinfo:
        card(None, {'shop_refreshes': value})
    assert message in str(excinfo.value)


@pytest.mark.parametrize('value, message', [
    ('100', 'must be the string "saved" or an integer'),
    (True, 'must be the string "saved" or an integer'),
    (100.0, 'must be the string "saved" or an integer'),
    (501, 'must be an integer 0..500'),
    (-1, 'must be an integer 0..500'),
])
def test_reserve_refuses_a_non_integer_or_an_out_of_range_value(value, message):
    with pytest.raises(ValueError) as excinfo:
        card(None, {'shop_reserve_coins': value})
    assert message in str(excinfo.value)


def test_a_stored_value_is_validated_too():
    with pytest.raises(ValueError, match='must be the string "saved" or an integer'):
        card({'shop_reserve_coins': '300'})
    with pytest.raises(ValueError, match='must be an integer 0..5'):
        card({'shop_refreshes': 9})


# --------------------------------------------------------------------- refusals

@pytest.mark.parametrize('kwargs, message', [
    ({'saved': {'shop_policy': 'automatic'}}, 'is not one of'),
    ({'saved': {'shop_policy': 3}}, 'must be one of'),
    ({'saved': {'shop_policy': True}}, 'must be one of'),
    ({'overrides': {'shop_policy': 'AUTO'}}, 'is not one of'),
    ({'overrides': {'shop_policy': ['manual']}}, 'must be one of'),
    ({'saved': {'unknown': 1}}, 'unknown field'),
    ({'overrides': {'nonsense': 1}}, 'unknown field'),
    ({'saved': ['shop_policy']}, 'must be a mapping'),
    ({'overrides': 'shop_policy'}, 'must be a mapping'),
])
def test_refusals(kwargs, message):
    with pytest.raises(ValueError) as excinfo:
        resolve_shop_settings(kwargs.get('saved'), kwargs.get('overrides'))
    assert message in str(excinfo.value)


def test_the_learning_layer_arguments_are_gone():
    import inspect

    signature = inspect.signature(resolve_shop_settings)
    assert list(signature.parameters) == ['saved', 'overrides']
    assert not any(name in signature.parameters
                   for name in ('evidence', 'keywords', 'retained_gift_rate'))


# --------------------------------------------------------------------- card contract

def test_the_card_carries_the_declared_fields_and_is_json_safe():
    result = card(None, {'shop_policy': 'learned', 'shop_refreshes': 5,
                         'shop_reserve_coins': 200})
    assert result['version'] == 1
    assert result['fields'] == list(FIELDS)
    assert set(FIELDS) <= set(result)
    for key, value in result.items():
        assert not isinstance(value, tuple), key
    json.dumps(result, allow_nan=False, sort_keys=True)
    assert json.loads(json.dumps(result)) == result


def test_the_resolver_does_not_mutate_its_arguments():
    saved = {'shop_policy': 'learned', 'shop_refreshes': 3, 'shop_reserve_coins': 200}
    overrides = {'shop_policy': 'learned', 'shop_refreshes': 5}
    before = (dict(saved), dict(overrides))
    card(saved, overrides)
    assert (saved, overrides) == before


def test_every_reason_the_resolver_emits_is_declared():
    cases = [(None, None),
             ({'shop_policy': 'learned', 'shop_refreshes': 3, 'shop_reserve_coins': 200},
              {'shop_policy': 'saved'}),
             (None, {'shop_policy': 'manual', 'shop_refreshes': 0, 'shop_reserve_coins': 0}),
             ({'shop_reserve_coins': 300}, {'shop_policy': 'learned',
                                            'shop_reserve_coins': 100}),
             ({'shop_reserve_coins': 100}, {'shop_policy': 'learned',
                                            'shop_reserve_coins': 300}),
             ({'shop_policy': 'saved', 'shop_refreshes': 'saved'}, {'shop_policy': 'saved'})]
    seen = set()
    for saved, overrides in cases:
        seen.update(card(saved, overrides)['reasons'])
    assert not sorted(reason for reason in seen if reason not in REASONS)


def test_reasons_and_choices_are_the_declared_vocabulary():
    assert set(POLICIES) == {'saved', 'manual', 'learned'}
    assert REFRESH_CHOICES[0] == RESERVE_CHOICES[0] == 'saved'
    assert max(item for item in REFRESH_CHOICES if item != 'saved') <= REFRESH_RANGE[1]
    assert max(item for item in RESERVE_CHOICES if item != 'saved') <= RESERVE_RANGE[1]
    assert all(isinstance(reason, str) and reason for reason in REASONS)


# --------------------------------------------------------------------- protocol

def test_the_protocol_states_the_same_contract_as_the_resolver():
    protocol = shop_settings_protocol()
    assert protocol['fields']['shop_policy'] == list(POLICIES)
    assert protocol['runtime_defaults'] == dict(RUNTIME_DEFAULTS)
    assert protocol['caps'] == {'shop_refreshes': REFRESH_CAP,
                                'shop_reserve_coins': RESERVE_CAP}
    assert protocol['learned']['obeys'] == list(LEARNED_OBEYS)
    assert protocol['learned']['decides_here'] is False
    assert 'lower the coin reserve floor' in protocol['learned']['never']
    json.dumps(protocol, allow_nan=False, sort_keys=True)


def test_the_protocol_documents_the_no_sample_fallback_and_the_strict_types():
    protocol = shop_settings_protocol()
    assert 'rule fallback' in protocol['learned']['without_samples']
    assert any('string of digits' in item for item in protocol['refuses'])
    assert any('float' in item for item in protocol['refuses'])


# --------------------------------------------------------------------- inert nodes

def test_collect_reads_the_three_inert_nodes_and_resolves_them():
    nodes = {
        'MirrorShopPolicy': {'attach': {'shop_policy': 'learned'}},
        'MirrorShopRefreshLimit': {'attach': {'shop_refreshes': 3}},
        'MirrorShopCoinReserve': {'attach': {'shop_reserve_coins': 'saved'}},
    }
    result = collect(nodes.__getitem__, {'shop_reserve_coins': 500})
    assert (result['shop_policy'], result['shop_refreshes'],
            result['shop_reserve_coins']) == ('learned', 3, 500)
    assert result['policy_source'] == 'manual' and result['refresh_source'] == 'manual'


def test_collect_with_every_node_left_at_saved_is_the_untouched_install():
    nodes = {name: {'attach': {field: 'saved'}} for name, field in (
        ('MirrorShopPolicy', 'shop_policy'), ('MirrorShopRefreshLimit', 'shop_refreshes'),
        ('MirrorShopCoinReserve', 'shop_reserve_coins'))}
    result = collect(nodes.__getitem__)
    assert (result['shop_policy'], result['shop_refreshes'],
            result['shop_reserve_coins']) == ('manual', 2, 0)
    assert result['learned_applied'] is False
