"""The settle loop may not read with an unbounded deadline.

Negative case: the 383 s gap in
`evidence/runtime/packaged-mirror-20261023-134753` happened because a re-read ran with
`deadline=None` and nothing wrote an event while it waited.
"""

import time

from maalimbus import runner


def _patch_observe(monkeypatch, record, sha="same"):
    def fake(observer, deadline=None):
        record.append(deadline)
        return {"image_sha256": sha}

    monkeypatch.setattr(runner, "observe", fake)


def test_a_round_without_a_caller_deadline_still_gets_one(monkeypatch):
    record = []
    _patch_observe(monkeypatch, record)
    now = time.monotonic()
    runner._settle(None, {"image_sha256": "same"}, "same", 3, 0, None)
    assert record, "the loop must read at least once"
    for deadline in record:
        assert deadline is not None, "an unbounded re-read is the defect"
        assert deadline <= now + runner.RE_SETTLE_LIMIT_S + 1


def test_a_caller_deadline_is_forwarded_unchanged(monkeypatch):
    record = []
    _patch_observe(monkeypatch, record)
    runner._settle(None, {"image_sha256": "same"}, "same", 2, 0, 12345.0)
    assert record and all(d == 12345.0 for d in record)


def test_a_changed_frame_stops_after_one_read(monkeypatch):
    record = []
    _patch_observe(monkeypatch, record, sha="different")
    after, changed = runner._settle(None, {"image_sha256": "same"}, "same", 5, 0, None)
    assert changed is True
    assert len(record) == 1


def test_every_round_is_announced(monkeypatch):
    record, rounds = [], []
    _patch_observe(monkeypatch, record)
    runner._settle(None, {"image_sha256": "same"}, "same", 3, 0, None,
                   on_round=rounds.append)
    assert rounds == [1, 2, 3], "a silent re-read is what made 383 s look like a hang"
