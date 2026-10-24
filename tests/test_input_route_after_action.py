"""An action task ends, the route goes with it, so the next input rebinds first.

Live `evidence/runtime/packaged-mirror-20261024-022543` (900 s budget, killed at
945.4 s): the entry task ended on `DRIVE`, the loop's next click left at 06:28:21,
MaaFW answered `unexpected msg [_ControllerPostClickReverseRequest controller_id=""]`
and then **nothing** happened for 781 s -- no journal row, no watchdog (the native call
never gives the interpreter back), until the harness killed the wrapper.  A read the
loop starts does not do that; only a task the loop starts itself ends by handing the
route back.  D86 therefore marks that moment and pays one `post_connection` before the
next input.
"""

from __future__ import annotations

import types

import pytest

from maalimbus import runner


class _Job:
    done = True
    succeeded = True


class _Controller:
    """A controller that records which framework calls reached it."""

    # The device asks a new controller for its screenshot policy before it uses it.
    set_screenshot_target_long_side = lambda self, *a, **k: None

    def __init__(self, *, refuse_connection=False):
        self.calls = []
        self.refuse_connection = refuse_connection

    def post_click(self, x, y):
        self.calls.append(('click', int(x), int(y)))
        return _Job()

    def post_swipe(self, x1, y1, x2, y2, duration):
        self.calls.append(('swipe', int(x1), int(y1), int(x2), int(y2)))
        return _Job()

    def post_connection(self):
        self.calls.append(('connection',))
        if self.refuse_connection:
            raise RuntimeError('the_controller_route_was_lost_and_rebinding_did_not_help')
        return _Job()


def _device(controller=None):
    return runner.MaaDevice(controller if controller is not None else _Controller())


def _loop(device, journal=None):
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.device = device
    loop.journal = journal
    loop.events = []
    return loop


def test_an_input_after_a_finished_task_rebinds_first():
    controller = _Controller()
    device = _device(controller)
    device.mark_action_ended()
    device.click(10, 20)
    assert controller.calls == [('connection',), ('click', 10, 20)]


def test_an_input_with_no_task_behind_it_does_not_rebind():
    controller = _Controller()
    _device(controller).click(10, 20)
    assert controller.calls == [('click', 10, 20)]


def test_only_the_next_input_pays_for_the_rebind():
    controller = _Controller()
    device = _device(controller)
    device.mark_action_ended()
    device.click(1, 2)
    device.click(3, 4)
    assert [call[0] for call in controller.calls] == ['connection', 'click', 'click']


def test_a_swipe_pays_it_too():
    controller = _Controller()
    device = _device(controller)
    device.mark_action_ended()
    device.swipe(1, 2, 3, 4, 100)
    assert [call[0] for call in controller.calls] == ['connection', 'swipe']


def test_a_rebind_that_cannot_connect_stops_the_input():
    controller = _Controller(refuse_connection=True)
    device = _device(controller)
    device.mark_action_ended()
    with pytest.raises(RuntimeError, match='route_was_lost'):
        device.click(10, 20)
    assert ('click', 10, 20) not in controller.calls


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
