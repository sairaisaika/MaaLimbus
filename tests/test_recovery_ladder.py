"""A step that did not land spends the recovery ladder before the run may end.

The live runs of 2026-10-15 stopped on one page shape after another -- a purchase
dialog whose badge the reader could not balance, a zoomed-in floor
(dist/MaaLimbus/evidence/runtime/pi-20261015-193010) whose nodes were off screen, a
skill check whose strip had not faded in yet. Each of those was a view, and a view
is moved by a gesture that presses nothing, so the runner no longer ends a run on
the first step that fails to land: it spends one rung of :data:`RECOVERY_LADDER`
per stop and ends the run only once that stop has spent the whole ladder.
"""
import json
import shutil
from pathlib import Path

import pytest

from maalimbus.runner import (MAP_ZOOM_OUT, RECOVERY_DRAG, RECOVERY_LADDER,
                              FakeDevice, FrameObserver, MirrorRunner, pinch_out)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'evidence/runtime/window-20261008-123839/frame-0001.json'


class TouchController:
    """The controller surface a pinch needs, recording every vector it is sent."""

    def __init__(self):
        self.events = []

    def post_touch_down(self, x, y, contact):
        self.events.append(('down', int(x), int(y), int(contact)))
        return 'job'

    def post_touch_move(self, x, y, contact):
        self.events.append(('move', int(x), int(y), int(contact)))
        return 'job'

    def post_touch_up(self, contact):
        self.events.append(('up', int(contact)))
        return 'job'


def map_window(tmp_path, frames=8, **settings):
    """A window walking one held map frame, with the run's own observed frames."""
    from test_runner import Notes
    if not SOURCE.exists():
        pytest.skip('the retained map frame is not present')
    paths = []
    for index in range(frames):
        source = tmp_path / f'source-{index}.json'
        shutil.copyfile(SOURCE, source)
        shutil.copyfile(SOURCE.with_suffix('.png'), source.with_suffix('.png'))
        paths.append(str(source))
    device = FakeDevice()
    options = {'rounds': 1, 'interval': 0, 'map_tries': 1, 'page_tries': 1}
    options.update(settings)
    notes = Notes()
    runner = MirrorRunner(device, settings=options, directory=tmp_path / 'output',
                          observer=FrameObserver(tmp_path / 'output', paths),
                          journal=notes)
    runner.run_id = 'recovery-ladder'
    return runner, device, notes


def test_the_pinch_closes_two_fingers_towards_the_centre():
    """The first rung is a pinch-in, which is what the game reads as zooming out."""
    controller = TouchController()
    pinch_out(controller, lambda job, timeout=None: None)
    centre, radius = MAP_ZOOM_OUT['centre'], MAP_ZOOM_OUT['radius']
    down = [event for event in controller.events if event[0] == 'down']
    moves = [event for event in controller.events if event[0] == 'move']
    up = [event for event in controller.events if event[0] == 'up']
    assert down == [('down', centre[0] - radius, centre[1], 0),
                    ('down', centre[0] + radius, centre[1], 1)]
    assert up == [('up', 0), ('up', 1)]
    assert len(moves) == 24 and [event[3] for event in moves[:2]] == [0, 1]
    spans = []
    for index in range(0, len(moves), 2):
        left = centre[0] - moves[index][1]
        right = moves[index + 1][1] - centre[0]
        assert left == right and left > 0, 'the fingers stay opposite each other'
        spans.append(left)
    assert spans == sorted(spans, reverse=True), 'the fingers only ever move inwards'
    assert spans[-1] == int(radius * MAP_ZOOM_OUT['factor'])


def test_a_controller_that_cannot_simulate_two_fingers_refuses_instead_of_clicking():
    class Tapper:
        def post_click(self, x, y):  # pragma: no cover - must never be reached
            raise AssertionError('a pinch must never fall back to a click')

    with pytest.raises(NotImplementedError):
        pinch_out(Tapper(), lambda job, timeout=None: None)


def test_every_rung_moves_the_view_and_none_of_them_presses_a_control(tmp_path):
    """The whole ladder is viewport-only, which is why it is safe on any page."""
    device = FakeDevice()
    runner = MirrorRunner(device, settings={'rounds': 1, 'interval': 0},
                          directory=tmp_path / 'output')
    for name, _ in RECOVERY_LADDER:
        runner._recovery_gesture(name)
    assert device.clicks == [], 'a recovery never presses a game control'
    assert device.pinches == [(tuple(MAP_ZOOM_OUT['centre']), MAP_ZOOM_OUT['radius'],
                               MAP_ZOOM_OUT['factor'], MAP_ZOOM_OUT['seconds'])]
    assert device.swipes == [(RECOVERY_DRAG[0], RECOVERY_DRAG[1],
                              RECOVERY_DRAG[2], RECOVERY_DRAG[3], 400),
                             (RECOVERY_DRAG[2], RECOVERY_DRAG[3],
                              RECOVERY_DRAG[0], RECOVERY_DRAG[1], 400)]


def test_a_map_that_will_not_move_is_pinched_out_before_the_run_stops(tmp_path):
    """The held map is not a stop any more: the first rung is spent on it."""
    runner, device, _ = map_window(tmp_path)
    for _ in range(6):
        runner.step()
        if device.pinches:
            break
    assert device.pinches, 'the run pinches the map out instead of stopping on it'


def test_the_map_view_moves_before_another_candidate_is_tried(tmp_path):
    """A stalled map click spends the pinch first, then falls back to another node.

    Live run pi-20261015-200848 clicked five map candidates in ninety seconds while
    ``Exploring Floor 3`` never changed, because the map was still zoomed in on the
    panel it had opened. The view move now comes first and the candidate retry second.
    """
    runner, device, notes = map_window(tmp_path, frames=60, map_tries=3)
    for _ in range(10):
        runner.step()
        if 'window_map_retry' in [event for event, _ in notes.events]:
            break
    events = [event for event, _ in notes.events]
    assert 'window_map_retry' in events, 'the candidate retry still happens'
    assert events.index('window_recovery') < events.index('window_map_retry')
    assert len(device.pinches) >= 1


def test_the_ladder_is_spent_once_per_stop_and_then_the_run_ends(tmp_path):
    """A page that refuses the whole ladder is a real stop, not an endless gesture."""
    runner, device, notes = map_window(tmp_path, frames=44)
    result = None
    for _ in range(12):
        result = runner.step()
        if result.get('done'):
            break
    assert len(device.pinches) == 1, 'the map is pinched out once, not every round'
    assert len(device.swipes) == 2, 'then the list is dragged each way, once'
    assert result and result.get('done') and result.get('stopped')
    events = [event for event, _ in notes.events]
    assert events.count('window_recovery') == len(RECOVERY_LADDER)
    assert 'window_recovery_exhausted' in events
