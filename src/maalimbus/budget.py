"""Budget gate for anything that spends Enkephalin or Modules (offline, pure).

The user's standing constraint is *module budget is 0 / pending*: until a budget
is explicitly handed over, nothing may be converted or refilled.  This module is
that gate.  It never talks to the game; a caller asks it first and only then
sends input, so a refusal here is the reason no click is sent.

Refusals, in the order they are checked:

* `budget_not_configured` — no budget object, or `status` is not `active`
  (the shipped table ships as `pending`, so the default answer is *no*),
* `budget_amount_must_be_positive` — the request is not a positive integer,
* `purpose_not_allowed` — the caller named a purpose the table does not list,
* `budget_zero` — an active budget of 0 still spends nothing,
* `budget_exhausted` / `request_exceeds_remaining` — the ledger is at or over it,
* `amount_not_multiple_of_step` — e.g. Modules only convert in whole steps.
"""

from __future__ import annotations

import json
from pathlib import Path

STATUSES = ('pending', 'active', 'closed')
PURPOSES = ('enkephalin_refill', 'module_conversion')
POLICY_VERSION = 1


class BudgetError(ValueError):
    """The budget table is not usable."""


def load_budget(path: str | Path) -> dict:
    """Load and validate a budget table."""
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise BudgetError('budget must be an object')
    if raw.get('version') != POLICY_VERSION:
        raise BudgetError('budget version must be %d' % POLICY_VERSION)
    status = raw.get('status')
    if status not in STATUSES:
        raise BudgetError('budget status must be one of %s' % (STATUSES,))
    budget = raw.get('module_budget')
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
        raise BudgetError('module_budget must be a non-negative integer')
    spent = raw.get('spent', 0)
    if not isinstance(spent, int) or isinstance(spent, bool) or spent < 0:
        raise BudgetError('spent must be a non-negative integer')
    step = raw.get('conversion_step', 1)
    if not isinstance(step, int) or isinstance(step, bool) or step < 1:
        raise BudgetError('conversion_step must be a positive integer')
    purposes = raw.get('allowed_purposes', list(PURPOSES))
    if not isinstance(purposes, list) or any(p not in PURPOSES for p in purposes):
        raise BudgetError('allowed_purposes must list known purposes')
    return {
        'version': POLICY_VERSION,
        'status': status,
        'module_budget': budget,
        'spent': spent,
        'conversion_step': step,
        'allowed_purposes': list(purposes),
        'note': raw.get('note'),
    }


def plan_spend(amount, *, budget: dict | None, spent: int | None = None,
               purpose: str = 'module_conversion') -> dict:
    """Answer whether `amount` may be spent, with the reason either way."""
    if budget is None or budget.get('status') != 'active':
        return dict(allowed=False, reason='budget_not_configured', amount=amount,
                    spent_before=None, spent_after=None, remaining_before=None)
    spent_before = budget['spent'] if spent is None else spent
    remaining = budget['module_budget'] - spent_before
    answer = dict(allowed=False, reason=None, amount=amount,
                  spent_before=spent_before, spent_after=spent_before,
                  remaining_before=remaining)
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        answer['reason'] = 'budget_amount_must_be_positive'
        return answer
    if purpose not in budget['allowed_purposes']:
        answer['reason'] = 'purpose_not_allowed'
        return answer
    if budget['module_budget'] == 0:
        answer['reason'] = 'budget_zero'
        return answer
    if remaining <= 0:
        answer['reason'] = 'budget_exhausted'
        return answer
    if amount > remaining:
        answer['reason'] = 'request_exceeds_remaining'
        return answer
    if amount % budget['conversion_step'] != 0:
        answer['reason'] = 'amount_not_multiple_of_step'
        return answer
    answer['allowed'] = True
    answer['reason'] = 'within_budget'
    answer['spent_after'] = spent_before + amount
    return answer


def apply_spend(amount, *, budget: dict | None, spent: int | None = None,
                purpose: str = 'module_conversion') -> dict:
    """`plan_spend` plus the ledger a caller should persist when it is allowed."""
    answer = plan_spend(amount, budget=budget, spent=spent, purpose=purpose)
    answer['spent_next'] = answer['spent_after'] if answer['allowed'] else answer['spent_before']
    return answer
