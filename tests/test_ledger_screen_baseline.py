"""D136: the screen's selected count and the run's picks are two counters.

A three-free gift page can arrive with a card already marked Owned and outlined, so the
reader reports chosen=1 before this run has clicked anything.  Measured 2026-10-24
(`packaged-mirror-20261024-160653`): a fresh ledger with selected=[] met chosen=1 and the
run stopped on floor_gift_pending_commit_or_counter_mismatch.
"""

import json
import json as _json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maalimbus.floor_gift_transaction import FloorGiftTransaction  # noqa: E402
from maalimbus.floor_gifts import Offer, Trial  # noqa: E402


def _offers(*, owned=False):
    return [Offer("Melted Eyeball", "melted_eyeball", frozenset(), (0, 0, 10, 10),
                  Trial(0, "none", 0), owned, "three_free_select_button", 0)]


def _fresh(tmp_path):
    path = tmp_path / "ledger.json"
    return FloorGiftTransaction(path)


def test_a_page_that_arrives_with_one_selected_is_not_a_mismatch(tmp_path):
    tx = _fresh(tmp_path)
    data = tx.prepare("s", _offers(owned=True), {"chosen": 1, "required": 1}, "frame-0001")
    assert data["screen_before"] == 1
    # the same page read again: chosen 1, nothing picked by this run -> consistent
    tx.prepare("s", _offers(owned=True), {"chosen": 1, "required": 1}, "frame-0002")


def test_a_second_selection_is_measured_against_the_baseline(tmp_path):
    tx = _fresh(tmp_path)
    tx.prepare("s", _offers(owned=True), {"chosen": 1, "required": 1}, "frame-0001")
    with pytest.raises(ValueError, match="counter_mismatch"):
        tx.prepare("s", _offers(owned=True), {"chosen": 2, "required": 1}, "frame-0002")


def test_a_page_that_arrives_empty_keeps_the_old_meaning(tmp_path):
    tx = _fresh(tmp_path)
    data = tx.prepare("s", _offers(), {"chosen": 0, "required": 1}, "frame-0001")
    assert data["screen_before"] == 0

def test_a_selection_with_no_owned_card_is_still_unattributed(tmp_path):
    tx = _fresh(tmp_path)
    with pytest.raises(ValueError, match="selected_without_scoped_evidence"):
        tx.prepare("s", _offers(), {"chosen": 1, "required": 1}, "frame-0001")


def test_a_ledger_without_a_baseline_learns_it_from_a_page_with_no_picks(tmp_path):
    tx = _fresh(tmp_path)
    tx.prepare("s", _offers(owned=True), {"chosen": 0, "required": 1}, "frame-0001")
    path = tmp_path / "ledger.json"
    body = _json.loads(path.read_text(encoding="utf-8"))
    body.pop("screen_before", None)          # a ledger written before the counter existed
    path.write_text(_json.dumps(body), encoding="utf-8")
    tx = FloorGiftTransaction(path)
    tx.prepare("s", _offers(owned=True), {"chosen": 1, "required": 1}, "frame-0002")
    assert _json.loads(path.read_text(encoding="utf-8"))["screen_before"] == 1
