from pathlib import Path

import pytest

from maalimbus.github_cache import GitHubState
from maalimbus.policies import EnemyBuff, Gift, ResourceBudget, RunLedger, Team, rank_enemy_buffs, rank_gifts


def test_lalc_gift_order_and_block_priority():
    team = Team(1, frozenset({'Bleed'}), allow=frozenset({'Blocked'}), block=frozenset({'Blocked'}))
    gifts = [Gift('Owned', frozenset({'Bleed'}), owned=True), Gift('Other', tier=4),
             Gift('Synergy', frozenset({'Bleed'})), Gift('Blocked'), Gift('Unknown', recognized=False)]
    assert [g['name'] for g in rank_gifts(gifts, team)] == ['Synergy', 'Other', 'Owned']


def test_enemy_buff_separate_from_gift_heuristic():
    buffs = [EnemyBuff('HP', hp_percent=50), EnemyBuff('Clash', clash_power=1), EnemyBuff('Unknown', known=False)]
    assert [b['name'] for b in rank_enemy_buffs(buffs, 5)] == ['HP', 'Clash']


@pytest.mark.parametrize('stamina,expected', [(None, 0), (19, 0), (39, 0), (40, 1), (100, 3)])
def test_module_reserve_and_cap(stamina, expected):
    assert ResourceBudget(reserve_stamina=20, max_modules=3).modules(stamina) == expected


def test_refill_budget_is_explicit_and_missing_values_fail_closed():
    assert not ResourceBudget().authorize_refill(lunacy=1000, cost=26, spent=0, refills=0)
    policy = ResourceBudget(refill_enabled=True, max_refills=2, max_lunacy=52, reserve_lunacy=100)
    assert policy.authorize_refill(lunacy=126, cost=26, spent=26, refills=1)
    for cost, lunacy, spent, refills in [(None, 1000, 0, 0), (26, None, 0, 0), (26, 125, 0, 0), (26, 1000, 27, 1), (26, 1000, 0, 2)]:
        assert not policy.authorize_refill(lunacy=lunacy, cost=cost, spent=spent, refills=refills)


def test_completion_needs_all_floors_reward_and_return_not_task_success():
    ledger = RunLedger((1, 8))
    ledger.cleared_floors.update({1, 2, 3, 4})
    ledger.final_victory = ledger.reward_received = ledger.entry_returned = True
    assert not ledger.complete()
    ledger.cleared_floors.add(5)
    ledger.entry_returned = False
    assert not ledger.complete()
    ledger.entry_returned = True
    assert ledger.complete()
    assert ledger.rotation == 1 and ledger.completed_runs == 1
    assert not ledger.complete()


def test_rate_limit_resume_survives_restart(tmp_path):
    state = GitHubState()
    state.response(429, {'Retry-After': '120', 'X-RateLimit-Reset': '500'}, None, 100)
    path = tmp_path / 'cache.json'
    state.save(path)
    loaded = GitHubState.load(path)
    assert loaded.status == 'rate_limited' and not loaded.due(504) and loaded.due(505)
    loaded.response(200, {'ETag': 'v1'}, {'tag_name': 'v0.1.0'}, 505)
    loaded.response(304, {}, None, 4105)
    assert loaded.status == 'cached' and loaded.payload['tag_name'] == 'v0.1.0'


def test_no_release_is_not_a_network_error_and_304_requires_cache():
    state = GitHubState()
    state.response(404, {}, None, 0)
    assert state.status == 'no_release'
    state.response(304, {}, None, 3600)
    assert state.status == 'cache_missing' and state.etag == ''
