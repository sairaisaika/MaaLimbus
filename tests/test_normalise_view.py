"""Centring ends on a measurement: centred, or out of rounds -- never on a count alone."""
from maalimbus.runner import normalise_view

SIZE = (1920, 1080)


def _drive(parties):
    queue = list(parties)
    log = {'zoom': 0, 'drag': []}

    def measure():
        return (queue[0] if len(queue) == 1 else queue.pop(0)), SIZE

    def zoom():
        log['zoom'] += 1

    def drag(dx, dy):
        log['drag'].append((dx, dy))
        if len(queue) > 1:
            queue.pop(0)

    return measure, zoom, drag, log


def test_a_centred_view_zooms_once_and_returns():
    measure, zoom, drag, log = _drive([(960, 540)])
    assert normalise_view(measure, zoom, drag) == {'centred': True, 'steps': []}
    assert log['zoom'] == 1 and log['drag'] == []


def test_an_offset_view_is_dragged_until_centred():
    measure, zoom, drag, log = _drive([(1400, 540), (960, 540)])
    assert normalise_view(measure, zoom, drag) == {'centred': True, 'steps': [(-440, 0)]}
    assert log['drag'] == [(-440, 0)]


def test_a_floor_that_never_centres_says_so_instead_of_looping():
    measure, zoom, drag, log = _drive([(1400, 540)])
    out = normalise_view(measure, zoom, drag, rounds=2)
    assert out['centred'] is False and len(out['steps']) == 2
