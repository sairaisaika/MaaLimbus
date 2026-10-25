"""D165: a budget too short to pay for a whole step ends the loop itself."""
import time
from types import SimpleNamespace

import maalimbus.pages as pages
import maalimbus.runner as runner


def test_the_loop_ends_itself_when_the_tail_cannot_pay_for_a_step():
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.observe_only = False
    loop.steps = 5
    loop.interval = 0.0
    loop.round_limit = 1
    loop.state = {'step': 0, 'session_ended': None}
    loop.journal = None
    loop.observer = None
    loop.log = None
    loop.device = SimpleNamespace(tasker=None)
    loop.artifacts = {'steps': [], 'clicks_sent': 0}
    loop.deadline = time.monotonic() + 5.0   # inside the last MIN_STEP_SECONDS
    loop.settings = runner.settings()
    loop._start_stall_watch = lambda: None
    loop.summary = lambda: {'passed': False}
    ended = []
    loop._end_session = lambda name, **fields: ended.append((name, fields))
    loop.run(steps=5, interval=0.0, round_limit=1, deadline=loop.deadline)
    assert [name for name, _ in ended] == ['the_budget_could_not_pay_for_another_step']
    assert 0.0 < ended[0][1]['remaining_s'] <= runner.MIN_STEP_SECONDS


def test_a_budget_with_room_still_walks_a_step():
    taken = []

    def fake_step(**fields):
        taken.append(fields)
        return {'result': {'passed': True}}

    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.observe_only = False
    loop.steps = 1
    loop.interval = 0.0
    loop.round_limit = 1
    loop.state = {'step': 0, 'session_ended': None}
    loop.journal = None
    loop.observer = None
    loop.log = None
    loop.device = SimpleNamespace(tasker=None)
    loop.artifacts = {'steps': [], 'clicks_sent': 0}
    loop.deadline = None
    loop.settings = runner.settings()
    loop._start_stall_watch = lambda: None
    loop.settings = runner.settings()
    loop._retire_watches = lambda: None
    loop.summary = lambda: {'passed': True}
    loop.step = fake_step
    loop.run(steps=1, interval=0.0, round_limit=1, deadline=None)
    assert taken, 'a budget with room must still walk a step'


def test_the_tail_is_far_below_a_step_budget_and_named():
    assert runner.MIN_STEP_SECONDS == 20.0
    assert runner.MIN_STEP_SECONDS < runner.DEEP_STEP_SECONDS
    assert 'the_budget_could_not_pay_for_another_step' in pages.STOP_KINDS
