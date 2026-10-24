"""A sent deployment input is waiting for its verification, not failing.

`evidence/runtime/packaged-mirror-20261024-105501`: the run clicked
`clear_inherited_participant_order_before_saved_deployment` on PRE_BATTLE_TEAM and then
ended at 35 s with `Unverified deployment input remains pending`, because the planner
raises that error while the previous input is unverified and the step's `except ValueError`
turned it into an ending. What is pending is the *verification*, not a decision: the loop
must spend a bounded read or two letting the page answer (D116).
"""
import pathlib

import maalimbus.runner as runner

SOURCE = pathlib.Path(runner.__file__).read_text(encoding='utf-8')


def test_the_bound_is_a_small_number_of_reads():
    assert runner.DEPLOYMENT_PENDING_WAITS == 4


def test_the_pending_message_gets_its_own_branch_and_not_the_ending():
    start = SOURCE.index("if text=='Unverified deployment input remains pending':")
    block = SOURCE[start:start + 1600]
    assert 'waiting=True' in block
    assert 'deployment_input_awaiting_verification' in block
    # The ending must still exist past the bound, or a real stall would spin forever.
    assert 'done=True' in block


def test_the_wait_does_not_send_anything():
    start = SOURCE.index("if text=='Unverified deployment input remains pending':")
    block = SOURCE[start:start + 1600]
    assert 'self._result(page,None,False,None,waiting=True' in block
    assert 'input_sent' not in block
