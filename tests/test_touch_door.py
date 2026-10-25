"""A pinch is an input too: it asks the same two questions every other door asks (D164)."""

import pytest

from maalimbus import runner


class _Touched:
    """A controller that records the touches it was asked to simulate."""

    id = 'abc'

    def __init__(self):
        self.touches = []

    def post_touch_down(self, x, y, contact):
        self.touches.append(('down', x, y, contact))
        return object()

    def post_touch_move(self, x, y, contact):
        self.touches.append(('move', x, y, contact))
        return object()

    def post_touch_up(self, contact):
        self.touches.append(('up', contact))
        return object()


def _device(controller):
    device = object.__new__(runner.MaaDevice)
    device.controller = controller
    device.state = {}
    device.tasker = None
    device.last_input_error = None
    device.ended = None
    device.binding_lost = None
    device.deadline = None
    device._wait = lambda job, timeout=None: True
    return device


def test_a_pinch_on_a_healthy_controller_still_moves_two_fingers():
    controller = _Touched()
    device = _device(controller)
    device.pinch((960, 540), 320, 0.55, seconds=0.05)
    assert [touch[0] for touch in controller.touches].count('down') == 2
    assert [touch[0] for touch in controller.touches].count('up') == 2


def test_a_pinch_after_the_session_ended_is_refused_before_any_touch():
    controller = _Touched()
    device = _device(controller)
    device.ended = 'the session ended'
    with pytest.raises(RuntimeError, match='session ended'):
        device.pinch((960, 540), 320, 0.55, seconds=0.05)
    assert controller.touches == []


def test_a_pinch_with_a_lost_route_is_refused_by_name_before_any_touch():
    controller = _Touched()
    device = _device(controller)
    device.binding_lost = runner.BINDING_GONE_AFTER_A_TORN_TASK
    with pytest.raises(RuntimeError, match='released_when_the_task_was_torn_down'):
        device.pinch((960, 540), 320, 0.55, seconds=0.05)
    assert controller.touches == []


def test_the_guard_is_the_door_the_other_inputs_use():
    assert hasattr(runner.MaaDevice, '_touch_door')
