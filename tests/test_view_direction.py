"""拖动方向与“别把我方推过头”都是测量（m19160/m19189）。"""
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


def test_a_party_at_the_top_is_pulled_down_not_pushed_further_up():
    # y=120/1080 = 0.11, above the band: content must move down, i.e. dy < 0.
    _, drags = _run([(960, 120), (960, 300), (960, 500), (960, 520)])
    assert drags and drags[0] < 0, drags


def test_a_party_at_the_bottom_is_pulled_up():
    _, drags = _run([(960, 1020), (960, 800), (960, 620), (960, 610)])
    assert drags and drags[0] > 0, drags


def test_it_stops_once_the_party_is_inside_the_band():
    out, drags = _run([(960, 120), (960, 600), (960, 620), (960, 625)])
    assert len(drags) == 1, drags
    assert out['dragged'] == 1


def test_the_band_is_never_the_whole_frame():
    source = (pathlib.Path(runner.__file__)).read_text(encoding='utf-8')
    body = source[source.index('def normalise_view'):source.index('def pinch_out')]
    assert 'band = (0.22, 0.88)' in body
