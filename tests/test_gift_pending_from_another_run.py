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

from maalimbus.floor_gift_transaction import FloorGiftTransaction


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
