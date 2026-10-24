"""D135: a taken pick is proven by the screen it left for.

Measured 2026-10-24: of every archived `select_takes_the_picked_floor_gifts` click with a
later read, 13 of 13 left `GIFT_PICK` and landed on `GIFT_GET`.  The old postcondition
demanded one more selected card on a page that no longer existed, so a normal pick could
only ever fail it.
"""

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maalimbus.floor_gift_transaction import FloorGiftTransaction  # noqa: E402


def _ledger(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({"scope": "s", "offer": "o", "required": 1, "selected": [],
                                "picked_owned": {}, "commit_sent": False, "receipts": [],
                                "substitutions": [], "completed": False, "proofs": [],
                                "history": [],
                                "pending": {"kind": "pick", "title": "Melted Eyeball",
                                            "before": 0, "proof": "x"}}), encoding="utf-8")
    return FloorGiftTransaction(path)


def test_the_received_gift_screen_is_the_receipt(tmp_path):
    tx = _ledger(tmp_path)
    tx.observe_pick_left("GIFT_GET", "frame-0001")
    data = json.loads(tx.path.read_text(encoding="utf-8"))
    assert data["selected"] == ["Melted Eyeball"]
    assert data["pending"] is None
    assert data["proofs"] == ["frame-0001"]


def test_a_page_that_does_not_carry_the_pick_away_still_fails(tmp_path):
    tx = _ledger(tmp_path)
    with pytest.raises(ValueError, match="postcondition_not_proven"):
        tx.observe_pick_left("GIFT_PICK", "frame-0001")


def test_the_successor_page_set_is_named():
    assert FloorGiftTransaction.POST_PICK_PAGES == ("GIFT_GET",)
