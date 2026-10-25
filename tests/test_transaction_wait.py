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
    assert 'self._end_session(ending,' in source
    assert 'SUBMIT_TRANSITION_UNREADABLE' in source
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
    assert 'ending,done=True' in source.replace(' ', '')
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
    body = source[start:source.index('def _submit_transition_wait')]
    assert 'unknown_blockers' in body
    # The rule is one *ending* per cause, not one diagnostic: D252's pause notice is the
    # only other note and it returns without ending anything (a battle animation is
    # evidence the game is alive).  The ending itself is still emitted exactly once.
    assert body.count("note('pending_transaction_wait_exhausted'") == 1
    assert body.count('note(') == 2
    pause = body.index("note('pending_transaction_paused_for_a_battle_animation'")
    assert body[pause:pause + 400].count('return False') >= 1


def test_a_submitted_turn_is_bounded_by_the_clock_and_not_by_a_count():
    """D97: three waits would have ended a run the game was still loading.

    The archive says a transition after the start click names a page in median 27 s
    (p90 54 s, slowest 143.9 s), so a pending deployment card is bounded by the clock.
    """
    loop = _loop(transaction_waits=1, submit_seconds=180)
    loop.state['unknown_blockers'] = ['Deployment_transaction.pending']
    for _ in range(6):
        assert loop._pending_transaction_wait() is False
    assert loop.state.get('transaction_waits', 0) == 0   # a count that does not apply
    assert loop.state['submit_since'] > 0
    # the clock is what ends it
    loop.state['submit_since'] = loop.state['submit_since'] - 181
    assert loop._pending_transaction_wait() is True
    name, fields = loop.notes[-1]
    assert name == 'pending_submit_wait_exhausted'
    assert fields['blocked_by'] == ['Deployment_transaction.pending']
    assert fields['waited'] > 180
    assert fields['limit'] == 180.0


def test_the_other_pending_cards_keep_their_count():
    loop = _loop(transaction_waits=1)
    loop.state['unknown_blockers'] = ['theme_transaction.receipt_pending']
    assert loop._pending_transaction_wait() is False
    assert loop._pending_transaction_wait() is True
    assert loop.notes[-1][0] == 'pending_transaction_wait_exhausted'
    assert 'submit_since' not in loop.state


def test_a_page_that_reads_clears_the_transition_clock():
    loop = _loop(submit_seconds=180)
    loop.state['unknown_blockers'] = ['Deployment_transaction.pending']
    assert loop._pending_transaction_wait() is False
    assert 'submit_since' in loop.state
    loop.state['unknown_blockers'] = []
    assert loop._pending_transaction_wait() is False
    assert 'submit_since' not in loop.state


def test_the_transition_budget_is_a_bounded_setting():
    assert runner.settings().submit_seconds == 180
    assert runner.settings({'submit_seconds': 30}).submit_seconds == 30
    with pytest.raises(ValueError):
        runner.settings({'submit_seconds': 0})
    with pytest.raises(ValueError):
        runner.settings({'submit_seconds': 901})


def test_the_transition_blocker_is_recognised_in_both_spellings():
    assert runner._is_transition_blocker('Deployment_transaction.pending')
    assert runner._is_transition_blocker('deployment_transaction.submit_pending')
    assert not runner._is_transition_blocker('theme_transaction.receipt_pending')
    assert not runner._is_transition_blocker('active.victory')


def test_the_ending_that_belongs_to_a_transition_has_its_own_name():
    assert runner.SUBMIT_TRANSITION_UNREADABLE == 'the_submitted_turn_never_showed_a_page'
    source = (ROOT / 'src/maalimbus/runner.py').read_text(encoding='utf-8')
    assert 'SUBMIT_TRANSITION_UNREADABLE' in source
    # one writer: the branch still ends through `_end_session`
    start = source.index('def _submit_transition_wait')
    body = source[start:source.index('def _explore_unknown')]
    assert '_end_session' not in body



def test_a_battle_animation_is_not_a_pending_transaction_deadlock():
    # D252: live `packaged-mirror-20261025-054458` sent 14 clicks, then sat on UNKNOWN
    # frames that were battle cutscenes with a transaction open, and ended
    # `the_outcome_of_a_pending_transaction_is_unreadable`.  A frame the reader named as an
    # animation is evidence the game is alive, so the counter stands still.
    loop = _loop()
    loop.state['unknown_blockers'] = ['Grace_transaction.pending']
    loop.state['battle_cutscene'] = True
    for _ in range(6):
        assert loop._pending_transaction_wait() is False
    assert int(loop.state.get('transaction_waits', 0)) == 0
    names = [row[0] for row in loop.notes]
    assert names.count('pending_transaction_paused_for_a_battle_animation') == 1


def test_a_moving_picture_also_pauses_the_counter():
    # D253: on `packaged-mirror-20261025-055035` only eleven frames were read as cutscenes,
    # so the other unreadable ones advanced the counter to exhaustion.  A frame that
    # differs from the previous one is evidence the game is alive, whatever it reads as.
    loop = _loop()
    loop.state['unknown_blockers'] = ['Grace_transaction.pending']
    loop.state['frame_changed'] = True
    for _ in range(6):
        assert loop._pending_transaction_wait() is False
    assert int(loop.state.get('transaction_waits', 0)) == 0
    loop.state['frame_changed'] = False
    loop.settings = runner.settings({'transaction_waits': 1})
    assert loop._pending_transaction_wait() is False      # first still frame counts
    assert loop._pending_transaction_wait() is True       # second exhausts the budget
