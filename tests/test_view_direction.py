"""拖动的方向是测量的，不是常数（m19160：我方被推到画面顶部，说明之前一直在往上推）。"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from maalimbus import runner


def _run(series, *, rounds=4):
    cursor = {'i': 0}
    drags = []

    def measure():
        index = min(cursor['i'], len(series) - 1)
        cursor['i'] += 1
        return series[index], (1920, 1080)

    def zoom():
        return None

    def drag(dx, dy):
        drags.append(dy)

    out = runner.normalise_view(measure, zoom, drag, rounds=rounds)
    return out, drags


def test_the_first_drag_moves_the_content_down_not_up():
    _, drags = _run([(960, 200), (960, 300), (960, 400), (960, 500)])
    assert drags and drags[0] < 0, 'a positive dy pushes the picture up -- that is what pinned the party to the top'


def test_a_drag_whose_answer_goes_the_other_way_flips_the_sign():
    _, drags = _run([(960, 400), (960, 340), (960, 300), (960, 280)])
    assert drags[0] < 0, drags
    assert any(d > 0 for d in drags[1:]), 'the party moved up after a downward drag, so the sign must flip: %r' % (drags,)


def test_it_stops_when_the_party_stops_moving():
    out, drags = _run([(960, 400), (960, 500), (960, 500), (960, 500)])
    assert len(drags) <= 2 and out['dragged'] == len(drags)
