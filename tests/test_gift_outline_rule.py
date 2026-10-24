"""D130: one card's outline is read from its sides, not from all four segments.

Measured 2026-10-24 on `evidence/runtime/packaged-mirror-20261024-144625/frame-0011.png`:
the three-free gift page showed its right card plainly selected (orange outline plus
`Owned`) while the card's **top** segment sat under the `Owned` / `Acquire E.G.O Gift`
bands.  The old rule required every segment to be lit and refused the page with
`three_free_gift_outline_ambiguous`, ending a run at 63 s.
"""
import json
from pathlib import Path

import cv2
import pytest

from maalimbus.floor_gifts import outline_state, single_free_selection_edges
from maalimbus.reward_vision import gift_cards
from maalimbus.vision import Text

ROOT = Path(__file__).resolve().parents[1]
FRAME = ROOT/'evidence/runtime/packaged-mirror-20261024-144625/frame-0011'


def test_a_covered_top_segment_does_not_hide_a_selection():
    assert outline_state([0.668, 0.502, 0.149, 0.473]) == 1


def test_a_covered_bottom_segment_is_the_same_reading():
    assert outline_state([0.6, 0.5, 0.4, 0.02]) == 1


@pytest.mark.parametrize('edges', [[0.0, 0.0, 0.0, 0.0], [0.01, 0.02, 0.0, 0.03]])
def test_nothing_lit_is_unselected(edges):
    assert outline_state(edges) == 0


def test_one_dark_side_against_a_lit_button_is_a_disagreement():
    # The sides are never covered, so a dark side is a different answer than a
    # covered top band -- the old test that forces the left segment dark stays red.
    assert outline_state([0.0, 0.5, 0.4, 0.4]) is None
    assert outline_state([0.6, 0.0, 0.4, 0.4]) is None


def test_a_single_lit_segment_is_a_frame_mid_sweep():
    assert outline_state([0.6, 0.0, 0.0, 0.0]) is None
    assert outline_state([0.02, 0.03, 0.30, 0.01]) is None


def test_no_measurement_is_not_a_state():
    for edges in (None, [], ()):
        assert outline_state(edges) is None


@pytest.mark.skipif(not FRAME.with_suffix('.png').exists(), reason='archived frame not kept')
def test_the_retained_frame_reads_two_dark_and_one_selected():
    data = json.loads(FRAME.with_suffix('.json').read_text(encoding='utf-8'))
    image = cv2.imread(str(FRAME.with_suffix('.png')))
    size = tuple(data.get('size') or (1920, 1080))
    records = [Text(r['text'], tuple(r['box']), r.get('score', 1.0)) for r in data['ocr']]
    boxes = gift_cards(records, size)
    states = [outline_state(single_free_selection_edges(image, box, size, bottom_span=110))
              for box in boxes]
    assert states == [0, 0, 1], states


def test_the_same_card_reads_the_same_at_a_smaller_picture_size():
    """D132: the packaged run captures 1280x720 while the record says 1920x1080.

    A probe placed at y=835 in the record's space falls outside a 720-high picture, so
    every card came back with no segments at all and the reader could only call it
    ambiguous.  The probes belong to the picture, not to the record.
    """
    import cv2
    import json as _json
    import pathlib as _pathlib

    from maalimbus.reward_vision import gift_cards
    from maalimbus.vision import Text

    path = (_pathlib.Path(__file__).resolve().parents[1]
            / "evidence/runtime/packaged-mirror-20261024-154637/frame-0001")
    data = _json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    image = cv2.imread(str(path.with_suffix(".png")))
    records = [Text(r["text"], tuple(r["box"]), r["score"]) for r in data["ocr"]]
    boxes = gift_cards(records, (1920, 1080))
    big = [outline_state(single_free_selection_edges(image, b, (1920, 1080), bottom_span=110))
           for b in boxes]
    small_image = cv2.resize(image, (1280, 720))
    small = [outline_state(single_free_selection_edges(small_image, b, (1920, 1080), bottom_span=110))
             for b in boxes]
    assert big == [0, 0, 1]
    assert small == big
