"""The view is pushed to the bottom edge, not centred (D290, operator m18974)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.runner import normalise_view  # noqa: E402


def _script(ys):
    frames = iter([(1012, y) for y in ys])
    last = {'p': (1012, ys[0])}
    calls = []

    def measure():
        try:
            last['p'] = next(frames)
        except StopIteration:
            pass
        return last['p'], (1920, 1080)

    def zoom():
        calls.append(('zoom',))

    def drag(dx, dy):
        calls.append(('drag', dx, dy))

    return measure, zoom, drag, calls


def test_the_view_is_zoomed_before_anything_is_dragged():
    measure, zoom, drag, calls = _script([300, 600, 900, 940])
    normalise_view(measure, zoom, drag)
    assert calls[0] == ('zoom',)


def test_dragging_stops_when_the_party_stops_moving():
    measure, zoom, drag, calls = _script([300, 600, 900, 940, 941, 941])
    result = normalise_view(measure, zoom, drag, rounds=6)
    assert result['dragged'] <= 4, result
    assert result['centred'] is False


def test_a_view_that_never_moves_does_not_loop_forever():
    measure, zoom, drag, calls = _script([300, 300, 300, 300])
    result = normalise_view(measure, zoom, drag, rounds=6)
    assert result['dragged'] == 1
    assert len([c for c in calls if c[0] == 'drag']) == 1


def test_an_unreadable_party_drags_nothing():
    calls = []
    result = normalise_view(lambda: (None, None), lambda: calls.append('zoom'),
                            lambda *a: calls.append('drag'))
    assert result['dragged'] == 0 and result['centred'] is None
