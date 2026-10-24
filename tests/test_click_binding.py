"""An input door must refuse a binding that cannot route it (D71).

The first authorised live run (evidence/runtime/packaged-mirror-20261023-221109) sent eight
clicks and lost the ninth: the agent log shows `controller not found [controller_id=]` for the
click at (966, 591), and the run then sat until the harness budget killed it. The guard that
existed only compared the id with the empty string, and the binding's id was `None`, so a
click that provably could not land was posted anyway.

Every door now asks one predicate, so the answer cannot differ between click, swipe and key,
and the flow path -- which posts through the raw controller -- asks it too.
"""

import pathlib
import types

import pytest

import maalimbus.runner as runner
from maalimbus.runner import MaaDevice, binding_is_empty

ROOT = pathlib.Path(__file__).resolve().parents[1]


class _Job:
    def __init__(self):
        self.done = True
        self.succeeded = True


class _Controller:
    def __init__(self, id):
        if id is not _MISSING:
            self.id = id
        self.clicks = []
        self.swipes = []
        self.keys = []

    def post_click(self, x, y):
        self.clicks.append((x, y))
        return _Job()

    def post_swipe(self, x1, y1, x2, y2, duration_ms):
        self.swipes.append((x1, y1, x2, y2, duration_ms))
        return _Job()

    def post_key(self, code):
        self.keys.append(code)
        return _Job()


_MISSING = object()


def _device(id):
    controller = _Controller(id)
    device = MaaDevice(controller, wait=lambda job, timeout=10, deadline=None: job,
                       target_long_side=0)
    return device, controller


def test_an_empty_string_id_refuses_the_click():
    device, controller = _device('')
    with pytest.raises(RuntimeError, match='the_controller_binding_is_empty'):
        device.click(966, 591)
    assert controller.clicks == []


def test_a_none_id_refuses_the_click():
    """The live regression: `None` is not `''`, and it reaches the framework as ``."""
    device, controller = _device(None)
    assert device.binding_is_empty() is True
    with pytest.raises(RuntimeError, match='the_controller_binding_is_empty'):
        device.click(966, 591)
    assert controller.clicks == []


def test_a_bound_controller_still_posts():
    device, controller = _device('1943769088')
    device.click(640, 360)
    assert controller.clicks == [(640, 360)]


def test_a_stub_without_an_id_is_not_accused():
    """A stand-in that cannot answer "is the binding empty?" is let through, not accused."""
    device, controller = _device(_MISSING)
    assert device.binding_is_empty() is False
    device.click(10, 20)
    assert controller.clicks == [(10, 20)]


def test_swipe_and_key_refuse_the_same_binding():
    device, controller = _device(None)
    with pytest.raises(RuntimeError, match='the_controller_binding_is_empty'):
        device.swipe(1, 2, 3, 4, 600)
    with pytest.raises(RuntimeError, match='the_controller_binding_is_empty'):
        device.key(4)
    assert controller.swipes == []
    assert controller.keys == []


def test_the_predicate_is_one_answer_for_every_door():
    assert binding_is_empty(types.SimpleNamespace(id='')) is True
    assert binding_is_empty(types.SimpleNamespace(id=None)) is True
    assert binding_is_empty(types.SimpleNamespace(id='abc')) is False
    assert binding_is_empty(types.SimpleNamespace()) is False
    assert runner.EMPTY_BINDINGS == ('', None)


def test_the_flow_click_path_asks_before_it_posts():
    """run_flow posts through the raw controller, so it needs the guard too."""
    source = (ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    body = source.split('def run_flow', 1)[1]
    head = body.split('on_soft=lambda', 1)[0]
    assert 'binding_is_empty(controller)' in head
    assert "raise RuntimeError('the_controller_binding_is_empty')" in head
    # and it is asked before the click is posted
    assert head.index('binding_is_empty(controller)') < head.index('post_click')
