"""The budget gate must refuse by default and only allow what is explicitly given."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maalimbus.budget import (
    BudgetError,
    apply_spend,
    load_budget,
    plan_spend,
)

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / 'assets' / 'resource' / 'base' / 'budget.json'


def shipped():
    return load_budget(SHIPPED)


def active(**overrides):
    table = dict(shipped(), status='active', module_budget=5, spent=0)
    table.update(overrides)
    return table


def test_the_shipped_budget_refuses_everything_while_it_is_pending_or_zero():
    table = shipped()
    assert table['status'] == 'pending'
    assert table['module_budget'] == 0
    pending = plan_spend(4, budget=table)
    assert pending['allowed'] is False and pending['reason'] == 'budget_not_configured'
    zero = plan_spend(1, budget=active(module_budget=0))
    assert zero['allowed'] is False and zero['reason'] == 'budget_zero'
    assert plan_spend(1, budget=None)['reason'] == 'budget_not_configured'


def test_a_bad_budget_table_is_rejected(tmp_path):
    bad = tmp_path / 'bad.json'
    for payload in (
        {'version': 1, 'status': 'sure', 'module_budget': 0},
        {'version': 1, 'status': 'active', 'module_budget': -1},
        {'version': 1, 'status': 'active', 'module_budget': 1, 'spent': -2},
        {'version': 1, 'status': 'active', 'module_budget': 1, 'conversion_step': 0},
        {'version': 1, 'status': 'active', 'module_budget': 1, 'allowed_purposes': ['teleport']},
        {'version': 2, 'status': 'active', 'module_budget': 1},
    ):
        bad.write_text(json.dumps(payload), encoding='utf-8')
        with pytest.raises(BudgetError):
            load_budget(bad)


def test_a_request_must_be_a_positive_integer_and_a_known_purpose():
    table = active()
    for amount in (0, -1, 1.5, True, '1', None):
        answer = plan_spend(amount, budget=table)
        assert answer['allowed'] is False
        assert answer['reason'] == 'budget_amount_must_be_positive'
    wrong = plan_spend(1, budget=table, purpose='free_stuff')
    assert wrong['allowed'] is False and wrong['reason'] == 'purpose_not_allowed'


def test_the_ledger_stops_at_the_budget_it_was_given():
    exhausted = plan_spend(1, budget=active(spent=5))
    assert exhausted['reason'] == 'budget_exhausted'
    assert exhausted['remaining_before'] == 0
    over = plan_spend(2, budget=active(spent=4))
    assert over['reason'] == 'request_exceeds_remaining'
    assert over['remaining_before'] == 1
    assert plan_spend(1, budget=active(spent=4), purpose='enkephalin_refill')['allowed'] is True


def test_an_allowed_spend_reports_the_ledger_a_caller_should_persist():
    answer = apply_spend(2, budget=active(spent=1), purpose='enkephalin_refill')
    assert answer['allowed'] is True
    assert answer['reason'] == 'within_budget'
    assert (answer['spent_before'], answer['spent_after'], answer['spent_next']) == (1, 3, 3)
    refused = apply_spend(9, budget=active(spent=1))
    assert refused['allowed'] is False
    assert refused['spent_next'] == 1
    assert refused['spent_after'] == 1


def test_a_step_gate_keeps_whole_modules_whole():
    stepped = active(module_budget=10, conversion_step=4)
    assert plan_spend(3, budget=stepped)['reason'] == 'amount_not_multiple_of_step'
    assert plan_spend(4, budget=stepped)['allowed'] is True
    assert plan_spend(8, budget=stepped)['allowed'] is True


def test_an_explicit_spent_argument_overrides_the_table_and_stays_pure():
    table = active(spent=0)
    assert plan_spend(3, budget=table, spent=4)['reason'] == 'request_exceeds_remaining'
    assert plan_spend(3, budget=table)['allowed'] is True
    assert table['spent'] == 0
