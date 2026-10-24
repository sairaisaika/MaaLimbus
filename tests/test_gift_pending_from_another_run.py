"""D143: a pending commit whose proof belongs to another run cannot be booked.

Measured on `evidence/runtime/packaged-mirror-20261024-163315`: the run started on
GIFT_GET with `pending {kind: commit, adopted: True, title: 'Melted Eyeball'}` whose proof
lived in `...-161620`, stopped after 9.3 s with `floor_gift_receipt_unknown_repeated_or_pending`
and sent no click.  The proof's directory is the evidence that the receipt was printed to
another process, so the pending is retired by path, never by clock.
"""
import json
import pathlib

import pytest

from maalimbus import floor_gift_transaction as gift_ledger
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.floor_gifts import Offer, Trial


def _ledger(path, proof, **extra):
    row = dict(scope="s", session={}, sequence=[], pending=None, submitted=[], selected=[],
               receipts=[], abandoned=[], offered=[], completed=False, commit_sent=True,
               screen_before=1)
    row['pending'] = proof
    row.update(extra)
    path.write_text(json.dumps(row), encoding="utf-8")
    return path


def test_a_pending_from_another_run_is_retired(tmp_path):
    mine = tmp_path / "run-b"
    mine.mkdir()
    other = tmp_path / "run-a" / "frame-0001.json"
    other.parent.mkdir()
    other.write_text("{}", encoding="utf-8")
    path = _ledger(tmp_path / "t.json", {"kind": "commit", "title": "Melted Eyeball",
                                         "adopted": True, "proof": str(other)})
    tx = FloorGiftTransaction(path)
    retired = tx.retire_from_another_run(mine)
    assert retired == dict(kind="commit", title="Melted Eyeball", proof=str(other),
                           reason="a_previous_run_left_it_open")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["pending"] is None
    assert saved["abandoned"][0]["intent"] == "retire"


def test_a_pending_from_this_run_is_kept(tmp_path):
    mine = tmp_path / "run-b"
    mine.mkdir()
    proof = mine / "frame-0003.json"
    proof.write_text("{}", encoding="utf-8")
    path = _ledger(tmp_path / "t.json", {"kind": "commit", "proof": str(proof)})
    assert FloorGiftTransaction(path).retire_from_another_run(mine) is None
    assert json.loads(path.read_text(encoding="utf-8"))["pending"] is not None


def test_a_pending_with_no_proof_is_kept(tmp_path):
    path = _ledger(tmp_path / "t.json", {"kind": "commit"})
    assert FloorGiftTransaction(path).retire_from_another_run(tmp_path) is None


def test_no_pending_is_not_an_event(tmp_path):
    path = _ledger(tmp_path / "t.json", None)
    assert FloorGiftTransaction(path).retire_from_another_run(tmp_path) is None


def test_a_receipt_pending_is_retired_too(tmp_path):
    other = tmp_path / "run-a" / "frame-0002.json"
    other.parent.mkdir()
    other.write_text("{}", encoding="utf-8")
    mine = tmp_path / "run-b"
    mine.mkdir()
    path = _ledger(tmp_path / "t.json", {"kind": "receipt", "title": "X", "proof": str(other)})
    assert FloorGiftTransaction(path).retire_from_another_run(mine)["kind"] == "receipt"


def test_a_retired_commit_owes_no_receipt(tmp_path):
    """D143: the commit was sent but its receipt belongs to another process.

    Measured on `evidence/runtime/packaged-mirror-20261024-163638`: the retirement fired
    (`stale_card_retired FloorGiftTransaction {kind: commit, title: 'Melted Eyeball'}`)
    and the run still stopped on `floor_gift_receipt_unknown_repeated_or_pending` with
    zero clicks, because a ledger that had sent a commit and held no pending looked
    inconsistent.  It is not: it is a commit whose proof is outside this run.
    """
    other = tmp_path / "run-a" / "frame-0001.json"
    other.parent.mkdir()
    other.write_text("{}", encoding="utf-8")
    mine = tmp_path / "run-b"
    mine.mkdir()
    path = _ledger(tmp_path / "t.json", {"kind": "commit", "title": "Melted Eyeball",
                                         "adopted": True, "proof": str(other)})
    tx = FloorGiftTransaction(path)
    assert tx.retire_from_another_run(mine) is not None
    reloaded = FloorGiftTransaction(path)
    assert reloaded.data["retired_commit"]["title"] == "Melted Eyeball"
    # no receipt to book, and no reason to stop
    assert reloaded.receipt_intent("Some Gift", mine / "frame-0009.json") is None


def test_a_commit_that_was_never_retired_still_refuses(tmp_path):
    path = _ledger(tmp_path / "t.json", None)
    tx = FloorGiftTransaction(path)
    with pytest.raises(ValueError):
        tx.receipt_intent("Some Gift", tmp_path / "frame-0009.json")


def test_the_runner_treats_a_retired_commit_as_satisfied(tmp_path):
    """The same rule, at the runner's own guard (line ~3809): it stops on
    `floor_gift_receipt_unknown_repeated_or_pending` when no notice can be attributed,
    and a retired commit has no notice to attribute."""
    other = tmp_path / "run-a" / "frame-0001.json"
    other.parent.mkdir()
    other.write_text("{}", encoding="utf-8")
    mine = tmp_path / "run-b"
    mine.mkdir()
    path = _ledger(tmp_path / "t.json", {"kind": "commit", "title": "Melted Eyeball",
                                         "adopted": True, "proof": str(other)})
    FloorGiftTransaction(path).retire_from_another_run(mine)
    data = json.loads(path.read_text(encoding="utf-8"))
    # the runner's condition, in one line: retired and no pending means nothing is owed
    assert data.get("retired_commit") and not (data.get("pending") or {})


def test_a_prepare_does_not_erase_a_field_about_the_ledger_itself(tmp_path):
    """D144: `prepare` builds this run's record, and the fields that describe the
    ledger -- its generation and an owed commit from another run -- belong to the file,
    not to the run.  Measured 2026-10-24: the marker was written at load and gone after
    a prepare on the same page."""
    other = tmp_path / "run-a" / "frame-0001.json"
    other.parent.mkdir()
    other.write_text("{}", encoding="utf-8")
    mine = tmp_path / "run-b"
    mine.mkdir()
    path = _ledger(tmp_path / "t.json", {"kind": "commit", "title": "Melted Eyeball",
                                         "adopted": True, "proof": str(other)})
    FloorGiftTransaction(path).retire_from_another_run(mine)
    # A previous transaction that did finish: the ledger's own state, not a pending one.
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["completed"] = True
    path.write_text(json.dumps(raw), encoding="utf-8")
    tx = FloorGiftTransaction(path)
    tx.prepare("37fc4d01", [Offer("Melted Eyeball", "Melted Eyeball", (), (100, 200, 240, 200), Trial(0, "none", 0), False, "three_free_select_button", 0)], {"chosen": 0, "required": 1}, mine / "frame-0002.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["retired_commit"] and data["schema"] == gift_ledger.SCHEMA
    assert data["selected"] == [] and data["commit_sent"] is False



def test_the_ledger_fields_survive_a_run_that_rebuilds_the_record(tmp_path):
    """D144 guarded by the class itself: the fields that describe the ledger are the
    ones `prepare` has to carry, and the run's own state is the one it resets."""
    assert gift_ledger.CARRIED_FIELDS == ('retired_commit',)
