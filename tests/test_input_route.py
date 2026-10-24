"""A refused input is carried by a task, because that is the route that keeps working.

D85 replaced the prediction with one repair: post, and if the framework refuses with a
controller error, bind again with `post_connection` and retry once.  Live
`packaged-mirror-20261024-025135` killed that: `post_connection` answered
`handle_controller_post_connection controller not found [req.controller_id=""]` -- the same
empty id that made the click fail -- and its job never came back, so the repair blocked
instead of helping, while the *reads* two seconds earlier had run fine through the very
same tasker with the very same empty id.

D87 therefore sends a refused input the way the reads already go: `post_task` with a
pipeline override that defines a one-node task for this point.
"""

import json
from pathlib import Path

import pytest

from maalimbus import pages, runner


class Job:
    def __init__(self, done=True, succeeded=True):
        self.done = done
        self.succeeded = succeeded


class Tasker:
    """A tasker that records what it was asked to run."""

    def __init__(self, *, succeeds=True):
        self.posted = []
        self.stopped = 0
        self.succeeds = succeeds

    def post_task(self, entry, override=None):
        self.posted.append((entry, override))
        return Job(succeeded=self.succeeds)

    def post_stop(self):
        self.stopped += 1
        return Job()


class Refusing:
    """A controller that refuses the first N inputs with a route error."""

    def __init__(self, refusals=1, message='controller not found [controller_id=""]'):
        self.refusals = refusals
        self.message = message
        self.clicks = []
        self.swipes = []
        self.bindings = 0
        self.cached_image = None
        self.id = None

    def post_click(self, x, y):
        if self.refusals > 0:
            self.refusals -= 1
            raise RuntimeError(self.message)
        self.clicks.append((x, y))
        return Job()

    def post_swipe(self, x1, y1, x2, y2, duration_ms):
        if self.refusals > 0:
            self.refusals -= 1
            raise RuntimeError(self.message)
        self.swipes.append((x1, y1, x2, y2, duration_ms))
        return Job()

    def post_connection(self):
        self.bindings += 1
        return Job()


def _device(controller, tasker=None):
    device = runner.MaaDevice.__new__(runner.MaaDevice)
    device.controller = controller
    device.ended = None
    device.binding_lost = None
    device.rebinds = 0
    device.pipeline_inputs = 0
    device.last_input_error = None
    device.clicks = []
    device.deadline = None
    device._wait = lambda job, timeout=10: job
    if tasker is not None:
        device.tasker = tasker
    return device


def test_a_refused_click_is_carried_by_a_task():
    controller = Refusing(refusals=1)
    tasker = Tasker()
    device = _device(controller, tasker)
    device.click(100, 200)
    assert controller.clicks == []
    assert controller.bindings == 0
    assert len(tasker.posted) == 1
    entry, override = tasker.posted[0]
    assert entry == 'MirrorPointClick'
    assert override == {'MirrorPointClick': runner.point_override(
        'MirrorPointClick', ('click', 100, 200))}
    assert override['MirrorPointClick']['target'] == [100, 200, 1, 1]
    assert device.pipeline_inputs == 1
    assert 'controller not found' in device.last_input_error


def test_a_refused_swipe_is_carried_as_a_swipe():
    controller = Refusing(refusals=1)
    tasker = Tasker()
    device = _device(controller, tasker)
    device.swipe(1, 2, 3, 4, 500)
    entry, override = tasker.posted[0]
    assert entry == 'MirrorPointSwipe'
    row = override['MirrorPointSwipe']
    assert row['action'] == 'Swipe'
    assert row['begin'] == [1, 2, 1, 1] and row['end'] == [3, 4, 1, 1]
    assert row['duration'] == 500


def test_a_task_that_fails_is_a_named_ending():
    controller = Refusing(refusals=1)
    tasker = Tasker(succeeds=False)
    device = _device(controller, tasker)
    with pytest.raises(runner.RouteLost) as raised:
        device.click(1, 2)
    assert raised.value.reason == runner.ROUTE_LOST
    assert device.pipeline_inputs == 0


def test_an_input_with_no_tasker_is_still_a_named_ending():
    controller = Refusing(refusals=1)
    device = _device(controller)
    with pytest.raises(runner.RouteLost, match='nothing can carry it'):
        device.click(1, 2)


def test_a_working_controller_is_never_carried_by_a_task():
    controller = Refusing(refusals=0)
    tasker = Tasker()
    device = _device(controller, tasker)
    device.click(3, 4)
    assert controller.clicks == [(3, 4)]
    assert tasker.posted == []
    assert device.pipeline_inputs == 0


def test_an_unrelated_error_is_not_carried_by_a_task():
    controller = Refusing(refusals=1, message='post_click needs a point')
    tasker = Tasker()
    device = _device(controller, tasker)
    with pytest.raises(RuntimeError) as raised:
        device.click(5, 6)
    assert not isinstance(raised.value, runner.RouteLost)
    assert tasker.posted == []
    assert controller.bindings == 0


def test_the_ending_has_a_kind():
    assert pages.kind_of(reason=runner.ROUTE_LOST) == 'refused_by_policy'
    assert runner.ROUTE_LOST in pages.STOP_KINDS


def test_the_walk_names_the_reason_and_the_carriers():
    """The ending is written where the loop can still say what happened."""
    source = __import__('inspect').getsource(runner.MirrorRunner._walk)
    handler = source[source.index('except RouteLost as error:'):]
    handler = handler[:handler.index('except (RuntimeError, OSError)')]
    assert "self.note('input_withheld'" in handler
    assert 'self._end_session(error.reason' in handler
    assert 'rebinds=' in handler
    assert 'pipeline_inputs=' in handler


def test_the_override_is_a_one_node_task_that_reads_nothing():
    row = runner.point_override('MirrorPointClick', ('click', 7, 8))
    assert row['recognition'] == 'DirectHit'
    assert row['action'] == 'Click'
    assert row['next'] == []
    assert row['target'] == [7, 8, 1, 1]


def test_the_input_nodes_are_named_once():
    with pytest.raises(KeyError):
        runner.PIPELINE_INPUT_NODES['key']
    assert set(runner.PIPELINE_INPUT_NODES) == {'click', 'swipe'}
    assert runner.PIPELINE_INPUT_WINDOW > 0
