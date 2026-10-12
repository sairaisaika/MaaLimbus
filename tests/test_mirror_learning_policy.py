"""Tests for the offline Mirror learning policy: scoring, refusals and the learned gate.

Every assertion here is about the module's own auditable contract:

* a static score and a learned score are reported separately, and the learned term is
  exactly zero whenever no eligible outcome backs the feature;
* an unknown question (unreadable caption, unknown sinner, missing successor, unpriced or
  unaffordable offer) refuses with a named reason instead of producing a number;
* an outcome only reaches the learned weights when ``strategy_training_eligible`` is True,
  and ``model_trained`` is never True.

No test starts a game, opens a window, reads a screenshot, sends input or trains anything.
"""
import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

from maalimbus import mirror_learning_policy as policy

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'assets' / 'resource' / 'base' / 'identity-catalog.json'
GIFT_PLAN = ROOT / 'assets' / 'resource' / 'base' / 'gift-plan.json'

KEYWORD_WEIGHTS = {'Bleed': 0.6, 'Sinking': 0.8, 'Vulnerable': 0.4}


@pytest.fixture(scope='module')
def catalog():
    return policy.load_identity_catalog(CATALOG)


@pytest.fixture(scope='module')
def plan():
    return policy.load_gift_plan(GIFT_PLAN)


@pytest.fixture
def fixture_catalog():
    """A tiny two-identity catalog with the same documented shape as the shipped one."""
    return policy.validate_identity_catalog({
        'version': 1,
        'identities': [
            {'id': 10101, 'sinner': 1, 'sinner_name': 'Yi Sang', 'name': 'Yi Sang',
             'buff_keywords': ['Sinking'], 'skills': [1010101, 1010102, 1010103]},
            {'id': 10201, 'sinner': 2, 'sinner_name': 'Faust', 'name': 'Faust',
             'buff_keywords': ['Bleed'], 'skills': [1020101, 1020102, 1020103]},
        ],
    })


def skill_args(fixture_catalog, **overrides):
    args = {
        'sinner_name': 'Yi Sang',
        'identity_id': 10101,
        'skill_id': 1010102,
        'caption': '(1) Deal 2 Sinking and 1 Vulnerable on hit.',
        'price': 77,
        'currency': 1008,
        'replaces': 1010101,
        'skill_captions': {1010101: '(1) Deal 1 Bleed on hit.'},
        'catalog': fixture_catalog,
        'successor': 'read',
        'keywords': ['Sinking'],
        'keyword_weights': KEYWORD_WEIGHTS,
    }
    args.update(overrides)
    return args


def assert_json_safe(value):
    """The value must already be plain JSON data: no NaN, no Infinity, no objects."""
    text = json.dumps(value, allow_nan=False, sort_keys=True)
    assert json.loads(text) == value
    for number in _floats(value):
        assert math.isfinite(number)


def _floats(value):
    if isinstance(value, float):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _floats(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _floats(item)


def assert_split(result):
    """Every score states the static part, the learned part and that no model was trained."""
    assert 'static_score' in result and 'learned_score' in result and 'score' in result
    assert result['model_trained'] is False
    assert isinstance(result['evidence'], list)
    if not result['refused']:
        assert result['score'] == pytest.approx(result['static_score'] + result['learned_score'])
        assert_json_safe(result)


def episode(**overrides):
    """One verified hard-clear episode outcome, all eligibility evidence present."""
    row = {
        'episode': 'ep-0001',
        'scope': '4734',
        'date': '2026-10-12',
        'floors': 5,
        'victory': True,
        'reward': True,
        'completion_verified': True,
        'reward_verified': True,
        'strategy_training_eligible': True,
        'progress': 120,
        'gift_picks': ['Wound Clerid'],
        'gift_keywords': ['Bleed'],
        'route_kinds': ['elite'],
        'shop_purchases': [],
        'skill_replacements': [],
    }
    row.update(overrides)
    return row


# --------------------------------------------------------------------------------------
# Static table and the identity catalog
# --------------------------------------------------------------------------------------

class TestStaticTable:
    def test_defaults_are_finite_and_complete(self):
        table = policy.read_weights()
        assert set(table) == set(policy.DEFAULT_STATIC)
        for value in table.values():
            assert math.isfinite(value)
        assert table == policy.DEFAULT_STATIC

    def test_override_merges_and_is_read_only_for_callers(self):
        table = policy.read_weights({'trial_weight': 2.5})
        assert table['trial_weight'] == 2.5
        assert table['gift_base'] == policy.DEFAULT_STATIC['gift_base']

    def test_unknown_weight_refuses(self):
        with pytest.raises(ValueError):
            policy.read_weights({'not_a_weight': 1.0})

    @pytest.mark.parametrize('bad', [float('nan'), float('inf'), 'x', None, True])
    def test_non_finite_weight_refuses(self, bad):
        with pytest.raises(ValueError):
            policy.read_weights({'trial_weight': bad})

    def test_route_kind_weights_match_the_shipped_policy_table(self):
        shipped = json.loads((ROOT / 'assets' / 'resource' / 'base' /
                              'route-policy.json').read_text(encoding='utf-8'))
        assert shipped['weights'] == policy.ROUTE_KIND_WEIGHTS
        assert set(policy.ROUTE_KINDS) == set(shipped['weights'])


class TestIdentityCatalog:
    def test_shipped_catalog_validates(self, catalog):
        assert catalog['version'] == 1
        assert len(catalog['identities']) > 100
        for identity in catalog['identities'].values():
            assert isinstance(identity['id'], int)
            assert 1 <= identity['sinner'] <= 13
            assert len(identity['skills']) >= 1

    def test_validates_the_real_shipped_shape(self, catalog):
        with pytest.raises(ValueError):
            policy.validate_identity_catalog({'version': 2, 'identities': []})
        with pytest.raises(ValueError):
            policy.validate_identity_catalog({'version': 1, 'identities': []})
        with pytest.raises(ValueError):
            policy.validate_identity_catalog(
                {'version': 1, 'identities': [{'id': 1, 'sinner': 1}]})
        with pytest.raises(ValueError):
            policy.validate_identity_catalog(
                {'version': 1, 'identities': [{'id': 1, 'sinner': 1, 'skills': [1, 1]}]})
        with pytest.raises(ValueError):
            policy.validate_identity_catalog(
                {'version': 1, 'identities': [{'id': 1, 'sinner': 99, 'skills': [1]}]})

    def test_duplicate_identity_refuses(self):
        with pytest.raises(ValueError):
            policy.validate_identity_catalog({
                'version': 1,
                'identities': [
                    {'id': 1, 'sinner': 1, 'skills': [11]},
                    {'id': 1, 'sinner': 1, 'skills': [12]},
                ],
            })

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(OSError):
            policy.load_identity_catalog(tmp_path / 'absent.json')

    def test_unreadable_file_raises(self, tmp_path):
        broken = tmp_path / 'identity-catalog.json'
        broken.write_text('[]', encoding='utf-8')
        with pytest.raises(ValueError):
            policy.load_identity_catalog(broken)


# --------------------------------------------------------------------------------------
# Gift plan
# --------------------------------------------------------------------------------------

class TestGiftPlan:
    def test_shipped_plan_validates_and_names_the_default_list(self, plan):
        assert plan['version'] == 1
        assert plan['order'] == ['Wound Clerid', 'Little and To-be-Naughty Plushie']
        assert policy.wanted(plan, 'Wound Clerid') == 'allowed'
        assert policy.wanted(plan, 'wound   clerid') == 'allowed'
        assert policy.wanted(plan, 'Unlisted Thing') == 'not_allowed'

    def test_an_empty_name_refuses_as_input(self, plan):
        with pytest.raises(ValueError):
            policy.wanted(plan, '')
        with pytest.raises(ValueError):
            policy.wanted(plan, None)

    def test_team_keyword_selects_that_teams_list(self):
        rupture = policy.load_gift_plan(GIFT_PLAN, keyword='Rupture')
        assert rupture['order'] == ['Barbed Lasso', 'Fluorescent Lamp']
        assert policy.wanted(rupture, 'Barbed Lasso') == 'allowed'
        assert policy.wanted(rupture, 'Wound Clerid') == 'not_allowed'

    def test_unknown_keyword_falls_back_to_default(self):
        unknown = policy.load_gift_plan(GIFT_PLAN, keyword='No Such Attribute')
        assert unknown['order'] == ['Wound Clerid', 'Little and To-be-Naughty Plushie']

    def test_blocked_list_wins_over_allowed(self):
        plan = policy.validate_gift_plan({'default': ['A', 'B'], 'teams': {}},
                                         blocked=['Cursed Thing'])
        assert policy.wanted(plan, 'Cursed Thing') == 'blocked'
        assert policy.wanted(plan, 'A') == 'allowed'

    @pytest.mark.parametrize('payload,blocked', [
        ({'default': ['A', 'a'], 'teams': {}}, ()),
        ({'default': ['A'], 'teams': {'bleed': ['A', 'a']}}, ()),
        ({'default': ['A'], 'teams': {'bleed': 'A'}}, ()),
        ({'default': ['A', 'B'], 'teams': {}}, ('B',)),
        ({'default': ['A'], 'teams': {}}, ('B', 'b')),
        ([], ()),
    ])
    def test_bad_plans_refuse_loudly(self, payload, blocked):
        with pytest.raises(ValueError):
            policy.validate_gift_plan(payload, blocked=blocked)

    def test_empty_plan_is_allowed_and_answers_nothing(self):
        plan = policy.validate_gift_plan({'default': [], 'teams': {}})
        assert policy.wanted(plan, 'Anything') == 'not_allowed'


# --------------------------------------------------------------------------------------
# Truncated captions
# --------------------------------------------------------------------------------------

class TestCaptionStatus:
    @pytest.mark.parametrize('caption', [
        '(1) Deal 2 Sinking on hit.',
        'Deal 2 Sinking on hit!',
        '(1) 命中时造成 2 层 Sinking。',
    ])
    def test_complete_captions(self, caption):
        complete, reason = policy.caption_status(caption)
        assert complete is True
        assert reason == 'caption_complete'

    @pytest.mark.parametrize('caption', [
        None, '', '   ', 42, '(1) Deal 2 Sinking on hit...', '(1) Deal 2 Sinking\u2026',
        '(1) Deal 2 Sinking on hit..', 'Deal 2 Sinking.',
    ])
    def test_incomplete_captions(self, caption):
        complete, reason = policy.caption_status(caption)
        assert complete is False
        assert reason.startswith('caption_')

    def test_every_incomplete_reason_is_named(self):
        assert policy.caption_status(None) == (False, 'caption_missing')
        assert policy.caption_status('Deal 2 Sinking on hit') == (False, 'caption_not_terminated')
        assert policy.caption_status('Deal 2 Sinking\u2026') == (False, 'caption_truncated')
        assert policy.caption_status('Deal 2 Sinking.') == (False, 'caption_too_short')
        assert policy.caption_status('Hit.\u3002') == (False, 'caption_too_short')


# --------------------------------------------------------------------------------------
# Gift utility
# --------------------------------------------------------------------------------------

class TestGiftUtility:
    def test_allowed_gift_scores_with_a_named_plan_reason(self, plan):
        row = policy.gift_utility('Wound Clerid', plan=plan)
        assert row['refused'] is False
        assert row['score'] == pytest.approx(policy.DEFAULT_STATIC['gift_base'] +
                                             policy.DEFAULT_STATIC['gift_preference'])
        assert 'plan_status=allowed' in row['reasons']
        assert row['learned_score'] == 0.0
        assert row['learned_reason'] == 'no_eligible_episodes'
        assert_split(row)

    def test_blocked_gift_refuses(self):
        plan = policy.validate_gift_plan({'default': ['A'], 'teams': {}}, blocked=['Cursed Thing'])
        row = policy.gift_utility('Cursed Thing', plan=plan)
        assert row['refused'] is True
        assert row['refusal'] == 'gift_blocked'
        assert 'plan_status=blocked' in row['evidence'] or any(
            'blocked' in item for item in row['evidence'])
        assert_split(row)

    def test_owned_gift_is_penalised(self, plan):
        fresh = policy.gift_utility('Wound Clerid', plan=plan)
        kept = policy.gift_utility('Wound Clerid', plan=plan, owned=True)
        assert kept['score'] < fresh['score']
        assert 'already_owned_penalty' in kept['evidence']

    def test_a_measured_image_score_is_the_base(self, plan):
        row = policy.gift_utility('Wound Clerid', plan=plan, image_score=180.0,
                                  image_source='frame-0173 level/base power')
        assert row['static_score'] == pytest.approx(180.0 + policy.DEFAULT_STATIC['gift_preference'])
        assert 'image_source=frame-0173 level/base power' in row['evidence']

    def test_trial_cost_subtracts_and_must_not_be_negative(self, plan):
        row = policy.gift_utility('Wound Clerid', plan=plan, trial_cost=10)
        assert row['static_score'] == pytest.approx(
            policy.DEFAULT_STATIC['gift_base'] + policy.DEFAULT_STATIC['gift_preference'] -
            10 * policy.DEFAULT_STATIC['trial_weight'])
        with pytest.raises(ValueError):
            policy.gift_utility('Wound Clerid', plan=plan, trial_cost=-1)

    def test_observed_keywords_add_a_bounded_learned_term(self, plan):
        row = policy.gift_utility('Wound Clerid', plan=plan, keywords=['Bleed'],
                                  keyword_weights={'Bleed': 0.6})
        assert row['learned_applied'] is True
        assert row['learned_score'] == pytest.approx(0.6 * policy.DEFAULT_STATIC['gift_learning_gain'])
        assert row['learned_reason'] == 'keyword_observations'

    def test_unobserved_keyword_contributes_exactly_nothing(self, plan):
        row = policy.gift_utility('Wound Clerid', plan=plan, keywords=['Unseen Mechanic'],
                                  keyword_weights={'Bleed': 0.6})
        assert row['learned_score'] == 0.0
        assert row['learned_applied'] is False
        assert row['learned_reason'] == 'keyword_unobserved'
        assert row['unknown_keywords'] == ['Unseen Mechanic']

    def test_no_keyword_weights_means_no_learning(self, plan):
        row = policy.gift_utility('Wound Clerid', plan=plan, keywords=['Bleed'])
        assert row['learned_score'] == 0.0
        assert row['learned_reason'] == 'no_eligible_episodes'

    @pytest.mark.parametrize('bad', [float('nan'), float('inf'), None, 'high'])
    def test_bad_image_score_refuses_as_input(self, plan, bad):
        with pytest.raises(ValueError):
            policy.gift_utility('Wound Clerid', plan=plan, image_score=bad)

    def test_empty_name_refuses_as_input(self, plan):
        with pytest.raises(ValueError):
            policy.gift_utility('', plan=plan)


# --------------------------------------------------------------------------------------
# Route scoring
# --------------------------------------------------------------------------------------

class TestRouteScore:
    def test_kind_weight_orders_the_eight_shipped_kinds(self):
        scores = {kind: policy.route_score(kind)['static_score'] for kind in policy.ROUTE_KINDS}
        assert scores['boss'] > scores['elite'] > scores['focused'] > scores['abnormality']
        assert scores['abnormality'] > scores['event'] > scores['regular'] > scores['shop']
        assert scores['shop'] > scores['empty']
        for row in (policy.route_score(kind) for kind in policy.ROUTE_KINDS):
            assert_split(row)

    def test_unknown_kind_refuses_with_a_named_reason(self):
        row = policy.route_score('mystery')
        assert row['refused'] is True
        assert row['refusal'] == 'route_kind_unknown'
        assert row['score'] == 0.0

    def test_wounded_leader_is_penalised(self):
        safe = policy.route_score('elite', hp_ratio=0.8)
        hurt = policy.route_score('elite', hp_ratio=0.1)
        assert hurt['static_score'] < safe['static_score']
        assert 'avoid_wounded' in hurt['reasons']
        assert policy.route_score('elite', hp_ratio=0.1,
                                  avoid_wounded=False)['static_score'] == safe['static_score']

    def test_last_floor_boss_is_pushed(self):
        assert 'push_boss_on_last_floor' in policy.route_score('boss', floor=5)['reasons']
        assert 'push_boss_on_last_floor' not in policy.route_score('boss', floor=4)['reasons']

    def test_single_candidate_fusion_shop_is_promoted(self):
        assert 'promote_fusion_shop' in policy.route_score('shop', candidates=1)['reasons']
        assert 'promote_fusion_shop' not in policy.route_score('shop', candidates=3)['reasons']

    @pytest.mark.parametrize('kwargs', [
        {'floor': 0}, {'floor': 6}, {'hp_ratio': -0.1}, {'hp_ratio': 1.5}, {'hp_ratio': 'x'},
    ])
    def test_out_of_domain_context_refuses_as_input(self, kwargs):
        with pytest.raises(ValueError):
            policy.route_score('elite', **kwargs)

    def test_explicit_kind_table_overrides_the_built_in_one(self):
        row = policy.route_score('empty', weights={'kinds': {'empty': 9.0}})
        assert row['static_score'] > policy.route_score('boss')['static_score']
        missing = policy.route_score('boss', weights={'kinds': {'empty': 9.0}})
        assert missing['refused'] is True
        assert missing['refusal'] == 'route_kind_unknown'


class TestRoutePlan:
    def test_orders_candidates_and_keeps_input_order_on_ties(self):
        candidates = [{'name': 'left', 'kind': 'regular'}, {'name': 'right', 'kind': 'regular'},
                      {'name': 'boss-door', 'kind': 'boss'}]
        route = policy.plan_route(candidates, floor=2)
        assert [row['name'] for row in route['rows']] == ['boss-door', 'left', 'right']
        assert route['chosen']['name'] == 'boss-door'
        assert route['refused'] is False
        assert_split(route)

    def test_one_unknown_kind_refuses_the_whole_plan(self):
        route = policy.plan_route([{'name': 'a', 'kind': 'regular'},
                                   {'name': 'b', 'kind': 'mystery'}])
        assert route['refused'] is True
        assert route['refusal'] == 'route_kind_unknown'
        assert route['rows'] == []
        assert route['chosen'] is None

    def test_empty_candidate_list_chooses_nothing(self):
        route = policy.plan_route([])
        assert route['refused'] is False
        assert route['rows'] == []
        assert route['chosen'] is None

    def test_malformed_candidates_refuse_as_input(self):
        with pytest.raises(ValueError):
            policy.plan_route('not a list')
        with pytest.raises(ValueError):
            policy.plan_route(['not an object'])
        with pytest.raises(ValueError):
            policy.plan_route([{'name': '', 'kind': 'boss'}])

    def test_learned_kind_weight_re_ranks_without_inventing_one(self):
        base = policy.new_knowledge_base()
        assert policy.plan_route([{'name': 'a', 'kind': 'regular'},
                                  {'name': 'b', 'kind': 'elite'}],
                                 knowledge_base=base)['rows'][0]['name'] == 'b'
        leaned = copy.deepcopy(base)
        leaned['weights'] = {('route_kind', 'regular'): 9.0}
        route = policy.plan_route([{'name': 'a', 'kind': 'regular'},
                                   {'name': 'b', 'kind': 'elite'}], knowledge_base=leaned)
        assert route['rows'][0]['name'] == 'a'
        assert route['learned_applied'] is True
        assert route['learned_reason'] == 'kind_observations'


# --------------------------------------------------------------------------------------
# Shop shelf
# --------------------------------------------------------------------------------------

class TestShopOffer:
    def test_affordable_offer_scores_statically(self, plan):
        row = policy.shop_offer({'name': 'Wound Clerid', 'price': 150}, currency=1008, plan=plan)
        assert row['refused'] is False
        assert row['static_score'] == pytest.approx(policy.DEFAULT_STATIC['shop_offer_base'])
        assert row['learned_score'] == 0.0
        assert_split(row)

    def test_keywords_move_only_the_learned_part(self, plan):
        plain = policy.shop_offer({'name': 'Wound Clerid', 'price': 150}, currency=1008, plan=plan)
        learned = policy.shop_offer({'name': 'Wound Clerid', 'price': 150}, currency=1008,
                                    plan=plan, keywords=['Bleed'],
                                    keyword_weights={'Bleed': 0.6})
        assert learned['static_score'] == plain['static_score']
        assert learned['learned_score'] == pytest.approx(
            0.6 * policy.DEFAULT_STATIC['shop_learning_gain'])

    @pytest.mark.parametrize('offer,currency,refusal', [
        ({'name': 'A', 'price': None}, 1008, 'shop_price_unknown'),
        ({'name': 'A', 'price': '150'}, 1008, 'shop_price_unknown'),
        ({'name': 'A', 'price': -1}, 1008, 'shop_price_unknown'),
        ({'name': 'A', 'price': 150}, None, 'shop_currency_unknown'),
        ({'name': 'A', 'price': 150}, -1, 'shop_currency_unknown'),
        ({'name': 'A', 'price': 1500}, 1008, 'shop_offer_unaffordable'),
    ])
    def test_unpriced_or_unaffordable_offers_refuse(self, offer, currency, refusal):
        row = policy.shop_offer(offer, currency=currency)
        assert row['refused'] is True
        assert row['refusal'] == refusal
        assert row['score'] == 0.0
        assert_split(row)

    def test_owned_offer_refuses_as_a_duplicate(self, plan):
        row = policy.shop_offer({'name': 'Wound Clerid', 'price': 150}, currency=1008, plan=plan,
                                owned_names=['wound clerid'])
        assert row['refused'] is True
        assert row['refusal'] == 'shop_duplicate_owned'

    def test_blocked_offer_refuses(self):
        plan = policy.validate_gift_plan({'default': [], 'teams': {}}, blocked=['Cursed Thing'])
        row = policy.shop_offer({'name': 'Cursed Thing', 'price': 150}, currency=1008, plan=plan)
        assert row['refused'] is True
        assert row['refusal'] == 'shop_offer_blocked'

    def test_identity_mismatch_refuses(self, plan):
        row = policy.shop_offer({'name': 'Wound Clerid', 'price': 150}, currency=1008, plan=plan,
                                expected='Something Else')
        assert row['refused'] is True
        assert row['refusal'] == 'shop_offer_identity_mismatch'

    def test_fusion_and_health_move_the_static_part(self, plan):
        plain = policy.shop_offer({'name': 'Wound Clerid', 'price': 150}, currency=1008, plan=plan)
        fused = policy.shop_offer({'name': 'Wound Clerid', 'price': 150}, currency=1008, plan=plan,
                                  fusion_pending=True)
        hurt = policy.shop_offer({'name': 'Wound Clerid', 'price': 150}, currency=1008, plan=plan,
                                 health_required=True)
        assert fused['static_score'] > plain['static_score']
        assert hurt['static_score'] < plain['static_score']

    def test_malformed_offer_refuses_as_input(self, plan):
        with pytest.raises(ValueError):
            policy.shop_offer('not an object', currency=1008)
        with pytest.raises(ValueError):
            policy.shop_offer({'name': '', 'price': 10}, currency=1008)


class TestShopPlan:
    def test_buy_order_is_affordable_first_and_deterministic(self, plan):
        offers = [
            {'name': 'Wound Clerid', 'price': 150},
            {'name': 'Too Expensive', 'price': 5000},
            {'name': 'Little and To-be-Naughty Plushie', 'price': 150},
        ]
        row = policy.shop_plan(offers=offers, currency=1008, plan=plan)
        assert [item['name'] for item in row['buy_order']] == [
            'Wound Clerid', 'Little and To-be-Naughty Plushie']
        assert row['buy_order'][0]['score'] == row['buy_order'][1]['score']
        assert len(row['priority']) == 3
        assert row['priority'][1]['refusal'] == 'shop_offer_unaffordable'
        assert_json_safe(row)

    def test_refresh_needs_an_unaffordable_offer_a_budget_and_a_known_price(self, plan):
        offers = [{'name': 'Wound Clerid', 'price': 150}]
        no_reason = policy.shop_plan(offers=offers, currency=1008, plan=plan,
                                     refresh_limit=2, refresh_cost=15)
        assert no_reason['refresh'] is False
        assert 'no_refused_offer' in no_reason['refresh_reasons']

        poor = [{'name': 'Too Expensive', 'price': 5000}]
        unknown = policy.shop_plan(offers=poor, currency=1008, plan=plan, refresh_limit=2)
        assert unknown['refresh'] is False
        assert 'refresh_price_unknown' in unknown['refresh_reasons']

        spent = policy.shop_plan(offers=poor, currency=1008, plan=plan, refresh_limit=1,
                                 refreshes_used=1, refresh_cost=15)
        assert spent['refresh'] is False
        assert 'refresh_budget_exhausted' in spent['refresh_reasons']

        payable = policy.shop_plan(offers=poor, currency=1008, plan=plan, refresh_limit=2,
                                   refresh_cost=15)
        assert payable['refresh'] is True
        assert 'refresh_affordable' in payable['refresh_reasons']

        too_dear = policy.shop_plan(offers=poor, currency=10, plan=plan, refresh_limit=2,
                                    refresh_cost=15)
        assert too_dear['refresh'] is False
        assert 'refresh_unaffordable' in too_dear['refresh_reasons']

    def test_refresh_can_be_disabled_by_the_caller(self, plan):
        row = policy.shop_plan(offers=[{'name': 'A', 'price': 5000}], currency=1008, plan=plan,
                               refresh_limit=2, refresh_cost=15, refresh_allowed=False)
        assert row['refresh'] is False
        assert 'refresh_disabled' in row['refresh_reasons']

    def test_keyword_refresh_price_is_considered(self, plan):
        row = policy.shop_plan(offers=[{'name': 'A', 'price': 5000}], currency=100,
                                     plan=plan, refresh_limit=2, keyword_refresh_cost=90)
        assert row['refresh'] is True

    @pytest.mark.parametrize('kwargs', [
        {'offers': 'nope', 'currency': 1008},
        {'offers': [], 'currency': 1008, 'refresh_limit': -1},
        {'offers': [], 'currency': 1008, 'refreshes_used': -1},
        {'offers': [], 'currency': None},
    ])
    def test_bad_plan_arguments_refuse_as_input(self, kwargs):
        with pytest.raises(ValueError):
            policy.shop_plan(**kwargs)


# --------------------------------------------------------------------------------------
# Skill replacement: the bounded policy
# --------------------------------------------------------------------------------------

class TestSkillValue:
    def test_value_needs_a_complete_caption_and_reports_the_unknown_keywords(self):
        row = policy.skill_value(keywords=['Sinking', 'Something New'],
                                 caption='(1) Deal 2 Sinking on hit.',
                                 keyword_weights={'Sinking': 0.8})
        assert row['complete'] is True
        assert row['known_keywords'] == ['Sinking']
        assert row['unknown_keywords'] == ['Something New']
        assert row['value'] == pytest.approx(policy.DEFAULT_STATIC['skill_base_weight'] +
                                             0.8 * policy.DEFAULT_STATIC['skill_buff_weight'])
        assert row['model_trained'] is False

    def test_a_keyword_with_no_observation_is_worth_exactly_nothing(self):
        bare = policy.skill_value(caption='(1) Deal 2 Sinking on hit.')
        unknown = policy.skill_value(keywords=['Sinking'], caption='(1) Deal 2 Sinking on hit.')
        assert unknown['value'] == pytest.approx(bare['value'])
        assert unknown['unknown_keywords'] == ['Sinking']

    def test_a_truncated_caption_returns_no_value(self):
        row = policy.skill_value(caption='(1) Deal 2 Sinking\u2026')
        assert row['value'] is None
        assert row['complete'] is False

    def test_read_texts_must_contain_the_caption(self):
        row = policy.skill_value(caption='(1) Deal 2 Sinking on hit.',
                                 texts=['(1) Something Else Entirely.'])
        assert row['value'] is None
        assert row['caption_reason'] == 'caption_not_in_read_texts'


class TestSkillReplacement:
    def test_a_fully_evidenced_replacement_scores_the_value_delta(self, fixture_catalog):
        row = policy.skill_replacement(**skill_args(fixture_catalog))
        assert row['refused'] is False
        assert row['score'] == pytest.approx(
            0.8 * policy.DEFAULT_STATIC['skill_buff_weight'])
        assert row['slot'] == 0
        assert row['identity_id'] == 10101
        assert row['sinner'] == 'Yi Sang'
        assert row['skill_id'] == 1010102
        assert row['replaces'] == 1010101
        assert row['price'] == 77
        assert row['currency'] == 1008
        assert row['caption_status'] == 'caption_complete'
        assert row['reasons'][0] == 'skill_replacement_bounded'
        assert_split(row)

    def test_delta_needs_the_displaced_caption(self, fixture_catalog):
        without = policy.skill_replacement(**skill_args(fixture_catalog, skill_captions=None))
        assert without['refused'] is False
        assert without['score'] == pytest.approx(without['static_score'])

    def test_missing_displaced_caption_refuses(self, fixture_catalog):
        row = policy.skill_replacement(**skill_args(fixture_catalog, skill_captions={}))
        assert row['refused'] is True
        assert row['refusal'] == 'skill_replaced_caption_missing'

    def test_truncated_displaced_caption_refuses(self, fixture_catalog):
        row = policy.skill_replacement(**skill_args(
            fixture_catalog, skill_captions={1010101: '(1) Deal 1 Bleed\u2026'}))
        assert row['refused'] is True
        assert row['refusal'] == 'skill_replaced_caption_incomplete'

    def test_a_replacement_worth_no_more_refuses(self, fixture_catalog):
        row = policy.skill_replacement(**skill_args(
            fixture_catalog,
            skill_captions={1010101: '(1) Deal 2 Sinking and 1 Vulnerable on hit.'},
            replaced_keywords=['Sinking', 'Vulnerable']))
        assert row['refused'] is True
        assert row['refusal'] == 'skill_replacement_no_gain'
        assert any(item.startswith('delta=') for item in row['evidence'])

    def test_a_displaced_slot_with_no_read_keywords_refuses_as_unpriced(self, fixture_catalog):
        row = policy.skill_replacement(**skill_args(fixture_catalog))
        assert row['refused'] is False
        assert row['score'] == pytest.approx(
            0.8 * policy.DEFAULT_STATIC['skill_buff_weight'])
        assert any(item == 'replaced_keywords=[]' for item in row['evidence'])

    @pytest.mark.parametrize('overrides,refusal', [
        ({'sinner_name': 'Nobody At All', 'identity_id': None, 'skill_id': 1, 'replaces': 1},
         'skill_sinner_unknown'),
        ({'sinner_name': 'Faust'}, 'skill_sinner_mismatch'),
        ({'skill_id': 99}, 'skill_not_bound_to_identity'),
        ({'replaces': 99}, 'skill_slot_not_bound_to_identity'),
        ({'replaces': 1010102}, 'skill_slot_same_as_replacement'),
        ({'successor': None}, 'skill_successor_unproven'),
        ({'successor': {'name': 'Earned Skill', 'verified': False}}, 'skill_successor_unproven'),
        ({'successor': {'name': 'Something Else'}}, 'skill_successor_mismatch'),
        ({'price': None}, 'skill_price_unknown'),
        ({'price': '77'}, 'skill_price_unknown'),
        ({'price': 2000}, 'skill_price_unaffordable'),
        ({'currency': None}, 'shop_currency_unknown'),
        ({'caption': '(1) Deal 2 Sinking on hit\u2026'}, 'skill_caption_truncated'),
        ({'caption': '(1) Deal 2 Sinking on hit'}, 'skill_caption_not_terminated'),
        ({'caption': ''}, 'skill_caption_missing'),
        ({'replacements_used': 1, 'max_replacements': 1}, 'skill_replacement_budget_exhausted'),
    ])
    def test_each_missing_element_refuses_with_its_own_reason(self, fixture_catalog, overrides,
                                                              refusal):
        row = policy.skill_replacement(**skill_args(fixture_catalog, **overrides))
        assert row['refused'] is True
        assert row['refusal'] == refusal
        assert row['score'] == 0.0
        assert row['learned_score'] == 0.0
        assert_split(row)

    def test_an_unknown_question_refuses_instead_of_guessing(self, fixture_catalog):
        row = policy.skill_replacement(**skill_args(
            fixture_catalog, caption=None, successor=None, price=None, currency=None))
        assert row['refused'] is True
        assert row['refusal'].startswith('skill_caption_')
        assert row['score'] == 0.0

    def test_catalog_is_required(self):
        row = policy.skill_replacement(**skill_args({}, catalog=None))
        assert row['refused'] is True
        assert row['refusal'] == 'skill_catalog_unavailable'

    def test_the_english_sinner_name_binds_the_localized_identity(self, catalog):
        identity = next(item for item in catalog['identities'].values()
                        if item['sinner'] == 1 and len(item['skills']) >= 2)
        row = policy.skill_replacement(
            sinner_name=identity['sinner_name'], identity_id=identity['id'],
            skill_id=identity['skills'][1], caption='(1) Deal 2 Bleed on hit.',
            price=77, currency=1008, replaces=identity['skills'][0],
            skill_captions={identity['skills'][0]: '(1) Deal 1 Bleed on hit.'},
            catalog=catalog, successor='read', keywords=['Bleed'],
            keyword_weights=KEYWORD_WEIGHTS)
        assert row['refused'] is False
        assert row['identity_id'] == identity['id']

    def test_the_localized_identity_name_also_binds(self, catalog):
        identity = next(item for item in catalog['identities'].values()
                        if len(item['skills']) >= 2)
        row = policy.skill_replacement(
            sinner_name=identity['name'], identity_id=identity['id'],
            skill_id=identity['skills'][1], caption='(1) Deal 2 Bleed on hit.',
            price=77, currency=1008, replaces=identity['skills'][0],
            skill_captions={identity['skills'][0]: '(1) Deal 1 Bleed on hit.'},
            catalog=catalog, successor='read', keywords=['Bleed'],
            keyword_weights=KEYWORD_WEIGHTS)
        assert row['refused'] is False

    @pytest.mark.parametrize('kwargs', [
        {'offers_per_visit': 0}, {'offers_per_visit': -1},
        {'replacements_used': -1}, {'max_replacements': -1},
        {'skill_captions': 'not a mapping'},
    ])
    def test_out_of_domain_arguments_refuse_as_input(self, fixture_catalog, kwargs):
        with pytest.raises(ValueError):
            policy.skill_replacement(**skill_args(fixture_catalog, **kwargs))


# --------------------------------------------------------------------------------------
# The learned gate: only a verified, eligible outcome may move a weight
# --------------------------------------------------------------------------------------

class TestKnowledgeBaseGate:
    def test_a_new_base_is_empty_and_says_no_model_was_trained(self):
        base = policy.new_knowledge_base()
        assert base['weights'] == {}
        assert base['model_trained'] is False
        assert base['knowledge']['episodes'] == 0
        summary = policy.policy_summary(base)
        assert summary['weights'] == {}
        assert summary['model_trained'] is False
        assert 'model trained' in summary['not_claimed']

    def test_an_eligible_outcome_derives_a_bounded_weight(self):
        base = policy.update_outcome(policy.new_knowledge_base(), episode())
        assert base['knowledge']['episodes'] == 1
        assert base['knowledge']['learning_eligible_episodes'] == 1
        assert set(base['weights']) == {('gift_keyword', 'Bleed'), ('route_kind', 'elite')}
        for value in base['weights'].values():
            assert -policy.LEARNED_ADJUST_CAP <= value <= policy.LEARNED_ADJUST_CAP
        assert base['model_trained'] is False
        assert base['sources'] == ['ep-0001@4734@2026-10-12']

    def test_a_censored_outcome_is_evidence_but_never_learning(self):
        censored = episode(strategy_training_eligible=False, censored=True)
        base = policy.update_outcome(policy.new_knowledge_base(), censored)
        assert base['knowledge']['episodes'] == 1
        assert base['knowledge']['learning_eligible_episodes'] == 0
        assert base['knowledge']['censored_episodes'] == 1
        assert base['weights'] == {}

    def test_eligibility_is_required_even_when_the_caller_omits_censoring(self):
        silently_ineligible = episode(strategy_training_eligible=False)
        base = policy.update_outcome(policy.new_knowledge_base(), silently_ineligible)
        assert base['weights'] == {}

    def test_an_eligible_outcome_without_any_interaction_derives_nothing(self):
        base = policy.update_outcome(policy.new_knowledge_base(), episode(
            gift_picks=[], gift_keywords=[], route_kinds=[], shop_purchases=[]))
        assert base['knowledge']['learning_eligible_episodes'] == 1
        assert base['weights'] == {}

    def test_the_update_does_not_mutate_the_state_it_was_given(self):
        base = policy.new_knowledge_base()
        snapshot = copy.deepcopy(base)
        policy.update_outcome(base, episode())
        assert base == snapshot

    def test_a_single_feature_never_runs_past_the_cap(self):
        base = policy.new_knowledge_base()
        for index in range(6):
            base = policy.update_outcome(base, episode(episode=f'ep-{index:04d}', floors=0,
                                                       victory=False, reward=False,
                                                       progress=0))
        for value in base['weights'].values():
            assert -policy.LEARNED_ADJUST_CAP <= value <= policy.LEARNED_ADJUST_CAP

    @pytest.mark.parametrize('overrides', [
        {'episode': ''},
        {'scope': ''},
        {'date': ''},
        {'floors': 6},
        {'floors': -1},
        {'floors': 2.5},
        {'progress': 999},
        {'victory': True, 'completion_verified': False},
        {'reward': True, 'reward_verified': False},
        {'route_kinds': ['mystery']},
        {'shop_purchases': [{'name': 'A', 'price': None}]},
        {'shop_purchases': [{'name': 'A', 'price': -1}]},
        {'skill_replacements': [{'sinner': 'A'}]},
        {'gift_keywords': 'Bleed'},
    ])
    def test_an_unauditable_outcome_refuses_as_input(self, overrides):
        with pytest.raises(ValueError):
            policy.update_outcome(policy.new_knowledge_base(), episode(**overrides))

    def test_malformed_state_refuses_as_input(self):
        with pytest.raises(ValueError):
            policy.update_outcome('not a state', episode())
        with pytest.raises(ValueError):
            policy.update_outcome({'version': 1}, episode())

    def test_verified_outcome_facts_are_folded_into_the_audit_trail(self):
        base = policy.update_outcome(policy.new_knowledge_base(), episode(
            shop_purchases=[{'name': 'Sharpened Shard', 'price': 150, 'keywords': ['Bleed']}],
            skill_replacements=[{'sinner': 'Yi Sang', 'skill_id': 1010102, 'replaces': 1010101,
                                 'price': 77, 'delta': 12.0, 'successor': 'read'}]))
        assert base['knowledge']['shop']['purchase_events'] == 1
        assert base['knowledge']['shop']['wins'] == 1
        assert base['knowledge']['shop']['skill_replacements'] == [{
            'sinner': 'Yi Sang', 'skill_id': 1010102, 'replaces': 1010101,
            'price': 77, 'delta': 12.0}]

    def test_knowledge_base_for_folds_a_series_in_order(self):
        base = policy.knowledge_base_for([episode(episode='ep-1'), episode(episode='ep-2')])
        assert base['knowledge']['episodes'] == 2
        assert base['sources'] == ['ep-1@4734@2026-10-12', 'ep-2@4734@2026-10-12']
        assert base['last_episode'] == 'ep-2'


class TestStrategyScore:
    def test_without_any_knowledge_the_learned_term_is_zero_and_named(self):
        row = policy.strategy_score(kind='gift', feature=('gift_keyword', 'Bleed'),
                                    static_score=100.0)
        assert row['score'] == pytest.approx(100.0)
        assert row['learned_score'] == 0.0
        assert row['learned_applied'] is False
        assert row['learned_reason'] == 'no_eligible_episodes'
        assert row['reasons'] == ['static_heuristic']
        assert_split(row)

    def test_an_unobserved_feature_is_never_assigned_a_guessed_weight(self):
        base = policy.update_outcome(policy.new_knowledge_base(), episode())
        row = policy.strategy_score(kind='shop', feature=('gift_keyword', 'Unseen Mechanic'),
                                    static_score=100.0, knowledge_base=base)
        assert row['learned_score'] == 0.0
        assert row['learned_reason'] == 'feature_unobserved'

    def test_an_observed_feature_adds_a_bounded_adjustment(self):
        base = policy.update_outcome(policy.new_knowledge_base(), episode())
        row = policy.strategy_score(kind='gift', feature=('gift_keyword', 'Bleed'),
                                    static_score=100.0, knowledge_base=base)
        assert row['learned_applied'] is True
        assert row['learned_reason'] == 'observed'
        assert 0.0 < row['learned_score'] <= policy.LEARNED_ADJUST_CAP * 100.0
        assert row['score'] == pytest.approx(row['static_score'] + row['learned_score'])
        assert any(item.startswith('learned_source=') for item in row['evidence'])
        assert_split(row)

    def test_a_zero_static_scale_yields_no_learned_scale(self):
        base = policy.update_outcome(policy.new_knowledge_base(), episode())
        row = policy.strategy_score(kind='gift', feature=('gift_keyword', 'Bleed'),
                                    static_score=0.0, knowledge_base=base)
        assert row['learned_score'] == 0.0
        assert row['learned_reason'] == 'static_scale_zero'

    def test_an_unknown_decision_kind_refuses_as_input(self):
        with pytest.raises(ValueError):
            policy.strategy_score(kind='teleport', feature=('gift_keyword', 'Bleed'),
                                  static_score=1.0)

    @pytest.mark.parametrize('bad', [float('nan'), float('inf')])
    def test_a_non_finite_static_score_refuses_as_input(self, bad):
        with pytest.raises(ValueError):
            policy.strategy_score(kind='gift', feature=('gift_keyword', 'Bleed'),
                                  static_score=bad)


# --------------------------------------------------------------------------------------
# The whole surface stays offline, read-only and JSON-safe
# --------------------------------------------------------------------------------------

class TestOfflineSurface:
    def test_the_module_does_not_import_any_runtime_or_device_dependency(self):
        source = Path(policy.__file__).read_text(encoding='utf-8')
        for forbidden in ('import subprocess', 'import socket', 'import ctypes', 'win32',
                          'pyautogui', 'MaaFramework', 'maafw', 'import requests',
                          'urllib.request', 'open(..., \'w\'', "open(..., \"w\""):
            assert forbidden not in source
        tree = __import__('ast').parse(source)
        imported = set()
        for node in __import__('ast').walk(tree):
            if isinstance(node, __import__('ast').Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, __import__('ast').ImportFrom) and node.module:
                imported.add(node.module)
        assert imported <= {'copy', 'json', 'math', 'pathlib', '__future__'}

    def test_the_module_only_writes_by_reading_named_paths(self):
        source = Path(policy.__file__).read_text(encoding='utf-8')
        for opener in ("open(", "'w'", '"w"', "'a'", '"a"', 'write_text', 'unlink', 'mkdir'):
            assert opener not in source

    def test_every_public_entry_point_returns_json_data(self, catalog, plan):
        base = policy.update_outcome(policy.new_knowledge_base(), episode())
        outputs = [
            policy.policy_summary(base),
            policy.gift_utility('Wound Clerid', plan=plan, keywords=['Bleed'],
                                keyword_weights={'Bleed': 0.6}),
            policy.route_score('boss', floor=5),
            policy.plan_route([{'name': 'a', 'kind': 'boss'}], knowledge_base=base),
            policy.shop_offer({'name': 'Wound Clerid', 'price': 150}, currency=1008, plan=plan),
            policy.shop_plan(offers=[{'name': 'A', 'price': 150}], currency=1008, plan=plan),
            policy.skill_value(caption='(1) Deal 2 Bleed on hit.', keywords=['Bleed'],
                               keyword_weights={'Bleed': 0.6}),
            policy.strategy_score(kind='gift', feature=('gift_keyword', 'Bleed'),
                                  static_score=100.0, knowledge_base=base),
        ]
        for row in outputs:
            assert row['model_trained'] is False
            assert_json_safe(row)

    def test_a_full_skill_replacement_result_is_json_data(self, catalog):
        identity = next(item for item in catalog['identities'].values()
                        if item['sinner'] == 1 and len(item['skills']) >= 2)
        row = policy.skill_replacement(
            sinner_name=identity['sinner_name'], identity_id=identity['id'],
            skill_id=identity['skills'][1], caption='(1) Deal 2 Bleed on hit.',
            price=77, currency=1008, replaces=identity['skills'][0],
            skill_captions={identity['skills'][0]: '(1) Deal 1 Bleed on hit.'},
            catalog=catalog, successor='read', keywords=['Bleed', 'Unknown Key'],
            keyword_weights={'Bleed': 0.6})
        assert row['refused'] is False
        assert row['known_keywords'] == ['Bleed']
        assert row['unknown_keywords'] == ['Unknown Key']
        assert row['model_trained'] is False
        assert_json_safe(row)

    def test_the_module_is_importable_without_side_effects(self):
        spec = importlib.util.spec_from_file_location('mirror_learning_policy_probe',
                                                      policy.__file__)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.POLICY_VERSION == policy.POLICY_VERSION
        assert module.policy_summary()['episodes'] == 0
