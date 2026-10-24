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


def test_a_page_that_arrived_satisfied_commits_without_a_pick(tmp_path):
    """D137: screen_before 1, selected [], required 1 -> the screen is the selection."""
    tx = _fresh(tmp_path)
    tx.prepare("s", _offers(owned=True), {"chosen": 1, "required": 1}, "frame-0001")
    assert tx.data["selected"] == ["Melted Eyeball"] and tx.data["adopted"] is True
    tx.commit("frame-0002")
    assert tx.data["pending"]["adopted"] is True and tx.data["commit_sent"] is True


def test_an_unsatisfied_page_still_cannot_commit(tmp_path):
    tx = _fresh(tmp_path)
    tx.prepare("s", _offers(), {"chosen": 0, "required": 1}, "frame-0001")
    with pytest.raises(ValueError, match="commit_not_ready"):
        tx.commit("frame-0002")


def test_one_pick_is_still_required_when_the_page_carried_nothing(tmp_path):
    tx = _fresh(tmp_path)
    tx.prepare("s", _offers(), {"chosen": 0, "required": 1}, "frame-0001")
    tx.intent("Melted Eyeball", {"chosen": 0, "required": 1}, "frame-0002")
    from maalimbus.floor_gifts import Offer, Trial
    offers = [Offer("Melted Eyeball", "melted_eyeball", frozenset(), (0, 0, 10, 10),
                    Trial(0, "none", 0), False, "three_free_select_button", 0)]
    tx.observe_pick(offers, {"chosen": 1, "required": 1}, "frame-0003")
    tx.commit("frame-0004")
    assert tx.data["pending"]["adopted"] is False


def test_an_adopted_selection_attributes_the_first_notice(tmp_path):
    """D139: an adopted pick has no printed substitution to look up beforehand."""
    tx = _fresh(tmp_path)
    tx.prepare("s", _offers(owned=True), {"chosen": 1, "required": 1}, "frame-0001")
    tx.commit("frame-0002")
    tx.receipt_intent("Faint Vestige", "frame-0003", on_notice_page=True)
    pending = tx.data["pending"]
    assert pending["kind"] == "receipt" and pending["title"] == "Melted Eyeball"
    assert pending.get("printed") == "Faint Vestige"


def test_an_adopted_selection_without_a_notice_still_refuses(tmp_path):
    tx = _fresh(tmp_path)
    tx.prepare("s", _offers(owned=True), {"chosen": 1, "required": 1}, "frame-0001")
    tx.commit("frame-0002")
    with pytest.raises(ValueError, match="receipt_unknown_repeated_or_pending"):
        tx.receipt_intent("", "frame-0003", on_notice_page=False)


def test_a_ledger_written_before_adoption_still_attributes_its_commit(tmp_path):
    """D140: `selected` was empty in ledgers written before D138; the commit's own title answers."""
    tx = _fresh(tmp_path)
    tx.prepare("s", _offers(owned=True), {"chosen": 1, "required": 1}, "frame-0001")
    tx.commit("frame-0002")
    data = tx.data
    data["selected"] = []          # the shape a pre-D138 ledger has on disk
    tx._write(data) if hasattr(tx, "_write") else None
    tx.path.write_text(__import__("json").dumps(data), encoding="utf-8")
    tx.receipt_intent("Some Other Gift", "frame-0003", on_notice_page=True)
    assert tx.data["pending"]["title"] == "Melted Eyeball"


def test_a_ledger_says_which_reader_wrote_it(tmp_path):
    """D141: the generation is recorded, so 'older' is a fact instead of an inference."""
    tx = _fresh(tmp_path)
    tx.prepare("s", _offers(owned=True), {"chosen": 1, "required": 1}, "frame-0001")
    on_disk = __import__("json").loads(tx.path.read_text(encoding="utf-8"))
    assert on_disk["schema"] == __import__("maalimbus.floor_gift_transaction", fromlist=["x"]).SCHEMA
    legacy = FloorGiftTransaction(tmp_path / "old.json")
    legacy.path.write_text(__import__("json").dumps({"scope": "s", "selected": [], "pending": None}), encoding="utf-8")
    assert FloorGiftTransaction(tmp_path / "old.json").schema == 1
