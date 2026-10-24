"""D133: when the run kept no picture, the `Owned` caption names the selected card.

Measured on `evidence/runtime/packaged-mirror-20261024-154637/frame-0001`: the badge is
printed at [1186, 218, 86, 30] for the card boxed at [1235, 238, 240, 200], i.e. left of
and above the card's corner, so a band inside the card never sees it.
"""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maalimbus.floor_gifts import observe_three_free          # noqa: E402
from maalimbus.gift_vision import GiftCatalog                  # noqa: E402
from maalimbus.vision import Text                              # noqa: E402

FRAME = ROOT / "evidence/runtime/packaged-mirror-20261024-154637/frame-0001"
BOXES = [[439, 250, 240, 200], [836, 248, 240, 200], [1235, 238, 240, 200]]


def _records(path=FRAME):
    data = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    return [Text(r["text"], tuple(r["box"]), r["score"]) for r in data["ocr"]], data["size"]


def _catalog():
    return GiftCatalog(ROOT / "assets/resource/base")


def test_the_retained_frame_names_its_selected_card_without_a_picture():
    records, _ = _records()
    offers, count = observe_three_free(records, (1920, 1080), _catalog(), BOXES, None, None)
    assert [o.title for o in offers] == ["Midwinter Nightmare", "Fractured Blade", "Melted Eyeball"]
    assert count == {"chosen": 1, "required": 1, "evidence": "owned_caption"}


def test_two_badges_are_not_a_selection():
    records, _ = _records()
    doubled = list(records) + [Text("Owned", (590, 180, 86, 30), 0.99)]
    with pytest.raises(ValueError, match="selection_ambiguous"):
        observe_three_free(doubled, (1920, 1080), _catalog(), BOXES, None, None)


def test_no_badge_at_all_is_not_a_selection():
    records, _ = _records()
    stripped = [r for r in records if r.text != "Owned"]
    with pytest.raises(ValueError, match="selection_ambiguous"):
        observe_three_free(stripped, (1920, 1080), _catalog(), BOXES, None, None)


def test_the_badge_band_is_outside_the_card_and_not_inside_it():
    records, _ = _records()
    # Same records, but the badge moved inside the card body: the reader must not
    # accept it there, because that is where the effect text lives.
    inside = [r for r in records if r.text != "Owned"]
    inside.append(Text("Owned", (1300, 300, 86, 30), 0.99))
    # Any refusal is acceptable here: a second word in the title band makes the title
    # ambiguous before the selection is even asked about.  What must not happen is a
    # reading that treats an in-card caption as the selection.
    with pytest.raises(ValueError):
        observe_three_free(inside, (1920, 1080), _catalog(), BOXES, None, None)
