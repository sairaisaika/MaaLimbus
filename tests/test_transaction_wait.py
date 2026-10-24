"""A wait that can spend the whole run has no budget (D96).

Measured on `evidence/runtime/packaged-mirror-20261024-053406`: 51
`unknown_exploration_waits_for_existing_transaction` rows plus 42 transition waits made
260 of the run's 346 attributed seconds, the run gained no floor, and it ended on the
generic `the_loop_waited_without_a_new_page` after forty loop waits -- a sentence about
patience, not about the transaction that was open.

Two rules follow, and both are tested here against the real gate:

1. the gate says **what** was open (`blocked_by=['deployment_transaction.submit_pending']`);
2. the blocked wait has its own small budget, and running out of it ends the run with a
   reason that carries the blocker, instead of spending the generic wait budget.
"""

import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import runner  # noqa: E402


class _Tx:
    def __init__(self, data=None, name=None):
        self.data = data or {}
        if name:
            self.name = name


class _Store:
    def __init__(self, active=None):
        self.data = {'active': active or {}}


def _loop(**settings):
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.settings = runner.settings(settings or {})
    loop.state = {'page': 'UNKNOWN', 'step': 1}
    loop.notes = []
    loop.store = _Store()
    # non-None, but nothing to choose: the gate is what we are testing
    loop.exploration = types.SimpleNamespace(choose=lambda record: None)
    loop.grace_transaction = _Tx()
    loop.initial_transaction = _Tx()
    loop.deployment_transaction = _Tx()
    loop.theme_transaction = _Tx()
    loop.floor_gift_transaction = _Tx()
    loop.shop_transaction = _Tx()
    loop.note = lambda name, **fields: loop.notes.append((name, fields))
    loop._observe = lambda **kw: {}
    return loop


def _gate(loop):
    """Run only the gate's own decision, through the real method."""
    return loop._explore_unknown({}, None, None)


def test_a_quiet_store_lets_the_explorer_run():
    loop = _loop()
    assert _gate(loop) is None
    assert loop.state['unknown_blockers'] == []
    assert [name for name, _ in loop.notes] == []


def test_an_open_submission_is_named():
    loop = _loop()
    loop.deployment_transaction = _Tx({'submit_pending': True}, name='deployment_transaction')
    assert _gate(loop) is None
    assert loop.state['unknown_blockers'] == ['deployment_transaction.submit_pending']
    name, fields = loop.notes[-1]
    assert name == 'unknown_exploration_waits_for_existing_transaction'
    assert fields['blocked_by'] == ['deployment_transaction.submit_pending']


def test_a_victory_flag_and_an_entry_are_named_too():
    loop = _loop()
    loop.store = _Store({'victory': True, 'phase': 'entry_pending'})
    assert _gate(loop) is None
    assert loop.state['unknown_blockers'] == ['active.victory', 'active.entry_pending']


def test_the_blocked_wait_gets_a_small_budget_not_the_loop_wait_budget():
    loop = _loop(transaction_waits=2)
    loop.state['unknown_blockers'] = ['theme_transaction.receipt_pending']
    assert loop._pending_transaction_wait() is False
    assert loop._pending_transaction_wait() is False
    assert loop._pending_transaction_wait() is True
    name, fields = loop.notes[-1]
    assert name == 'pending_transaction_wait_exhausted'
    assert fields['waited'] == 3
    assert fields['blocked_by'] == ['theme_transaction.receipt_pending']
    assert fields['limit'] == 2


def test_a_page_that_reads_clears_the_blocked_wait():
    loop = _loop(transaction_waits=1)
    loop.state['unknown_blockers'] = ['active.victory']
    assert loop._pending_transaction_wait() is False
    assert loop.state['transaction_waits'] == 1
    loop.state['unknown_blockers'] = []
    assert loop._pending_transaction_wait() is False
    assert loop.state['transaction_waits'] == 0


def test_the_ending_names_the_transaction_and_not_a_missing_step():
    """The first live test wrote `no_step_recorded`: the reason has to come from the
    branch, and `_end_session` is the one writer of it."""
    source = (ROOT / 'src/maalimbus/runner.py').read_text(encoding='utf-8')
    assert 'self._end_session(PENDING_TRANSACTION_UNREADABLE,' in source
    assert "blocked_by=list(state.get('unknown_blockers') or [])" in source
    # the helper itself must not end the session: one ending, one writer
    start = source.index('def _pending_transaction_wait')
    body = source[start:start + 1600]
    assert '_end_session' not in body


def test_a_loop_that_ends_on_a_blocker_writes_the_reason_it_was_given():
    loop = _loop()
    loop.state['session_ended'] = None
    wrote = loop._end_session(runner.PENDING_TRANSACTION_UNREADABLE,
                              blocked_by=['active.victory'], waited=4)
    assert wrote is True
    assert loop.state['session_ended'] == runner.PENDING_TRANSACTION_UNREADABLE
    name, fields = loop.notes[-1]
    assert name == 'mirror_session_ended'
    assert fields['reason'] == runner.PENDING_TRANSACTION_UNREADABLE
    assert fields['blocked_by'] == ['active.victory']
    assert fields['waited'] == 4
    # and it says so only once
    assert loop._end_session(runner.PENDING_TRANSACTION_UNREADABLE) is False


def test_the_ending_has_a_name_of_its_own():
    assert runner.PENDING_TRANSACTION_UNREADABLE == ('the_outcome_of_a_pending_transaction'
                                                     '_is_unreadable')
    source = (ROOT / 'src/maalimbus/runner.py').read_text(encoding='utf-8')
    assert 'PENDING_TRANSACTION_UNREADABLE,done=True' in source.replace(' ', '')
    assert 'blocked_by=blockers' in source


def test_the_budget_is_a_bounded_setting():
    assert runner.settings().transaction_waits == 3
    assert runner.settings({'transaction_waits': 0}).transaction_waits == 0
    with pytest.raises(ValueError):
        runner.settings({'transaction_waits': 99})
    with pytest.raises(ValueError):
        runner.settings({'transaction_waits': -1})


def test_the_gate_does_not_grow_a_new_ending_of_its_own():
    """One ending per cause: the blocked wait ends through the same session end."""
    source = (ROOT / 'src/maalimbus/runner.py').read_text(encoding='utf-8')
    start = source.index('def _pending_transaction_wait')
    body = source[start:start + 1600]
    assert 'unknown_blockers' in body
    assert body.count('note(') == 1
