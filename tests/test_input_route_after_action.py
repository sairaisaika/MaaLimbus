"""An action task ends and takes the route with it, so the next input is carried by a task.

Live `evidence/runtime/packaged-mirror-20261024-022543` (900 s budget, killed at 945.4 s):
the entry task ended on `DRIVE`, the loop's next click left at 06:28:21, MaaFW answered
`unexpected msg [_ControllerPostClickReverseRequest controller_id=""]` and then **nothing**
happened for 781 s -- no journal row, no watchdog, until the harness killed the wrapper.

D86 answered that with one `post_connection` before the next input, and live
`packaged-mirror-20261024-025135` showed the framework refusing *that* too, with a job that
never came back.  D87 keeps the moment and changes the answer: the input right after a task
the loop started itself is sent as a one-node task, not as a controller request.
"""

from __future__ import annotations

import types

import pytest

from maalimbus import runner


class _Job:
    def __init__(self, succeeded=True):
        self.done = True
        self.succeeded = succeeded


class _Controller:
    """A controller that records which framework calls reached it."""

    # The device asks a new controller for its screenshot policy before it uses it.
    set_screenshot_target_long_side = lambda self, *a, **k: None

    def __init__(self, *, refuse=False):
        self.calls = []
        self.refuse = refuse

    def post_click(self, x, y):
        if self.refuse:
            raise RuntimeError('controller not found [controller_id=""]')
        self.calls.append(('click', int(x), int(y)))
        return _Job()

    def post_swipe(self, x1, y1, x2, y2, duration):
        if self.refuse:
            raise RuntimeError('controller not found [controller_id=""]')
        self.calls.append(('swipe', int(x1), int(y1), int(x2), int(y2)))
        return _Job()

    def post_connection(self):
        self.calls.append(('connection',))
        return _Job()


class _Tasker:
    def __init__(self, succeeded=True):
        self.posted = []
        self.succeeded = succeeded

    def post_task(self, entry, override=None):
        self.posted.append((entry, override))
        return _Job(succeeded=self.succeeded)

    def post_stop(self):
        return _Job()


def _device(controller=None, tasker=None):
    device = runner.MaaDevice(controller if controller is not None else _Controller())
    if tasker is not None:
        device.tasker = tasker
    return device


def _loop(device, journal=None):
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.device = device
    loop.journal = journal
    loop.events = []
    return loop


def test_an_input_after_a_finished_task_goes_through_a_task():
    controller = _Controller()
    tasker = _Tasker()
    device = _device(controller, tasker)
    device.mark_action_ended()
    device.click(10, 20)
    assert controller.calls == []
    assert [entry for entry, _ in tasker.posted] == ['MirrorPointClick']
    assert tasker.posted[0][1]['MirrorPointClick']['target'] == [10, 20, 1, 1]
    assert device.pipeline_inputs == 1


def test_an_input_with_no_action_behind_it_goes_straight_to_the_controller():
    controller = _Controller()
    tasker = _Tasker()
    device = _device(controller, tasker)
    device.click(10, 20)
    assert controller.calls == [('click', 10, 20)]
    assert tasker.posted == []


def test_only_the_next_input_pays_for_it():
    controller = _Controller()
    tasker = _Tasker()
    device = _device(controller, tasker)
    device.mark_action_ended()
    device.click(1, 2)
    device.click(3, 4)
    assert controller.calls == [('click', 3, 4)]
    assert len(tasker.posted) == 1
    assert device.route_suspect is False


def test_a_swipe_pays_it_too():
    controller = _Controller()
    tasker = _Tasker()
    device = _device(controller, tasker)
    device.mark_action_ended()
    device.swipe(1, 2, 3, 4, 100)
    assert [entry for entry, _ in tasker.posted] == ['MirrorPointSwipe']
    assert controller.calls == []


def test_a_carrier_that_fails_stops_the_input():
    controller = _Controller(refuse=True)
    tasker = _Tasker(succeeded=False)
    device = _device(controller, tasker)
    device.mark_action_ended()
    with pytest.raises(runner.RouteLost):
        device.click(10, 20)
    assert controller.calls == []


def test_a_refusal_is_also_carried_even_after_the_mark_is_cleared():
    """The refusal is the second way to learn the route is gone (D85 kept)."""
    controller = _Controller(refuse=True)
    tasker = _Tasker()
    device = _device(controller, tasker)
    device.click(5, 6)
    assert [entry for entry, _ in tasker.posted] == ['MirrorPointClick']


def test_the_loop_marks_the_moment_a_node_action_ends():
    device = _device()
    # `MirrorRunner.tasker` is a read-only property that reads the device.
    device.tasker = types.SimpleNamespace(post_task=lambda name: _Job(), running=False)
    loop = _loop(device)
    loop.state = {'page': 'DRIVE'}
    loop.artifacts = {}
    loop.deadline = None
    loop.device = device
    device.route_suspect = False
    loop._act('MirrorDrive')
    assert device.route_suspect is True
