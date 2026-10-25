"""No read the loop waits on may outlive a bound, and a wedged one must end the run.

Negative case: the 383 s gap in
`evidence/runtime/packaged-mirror-20261023-134753` happened because a re-read ran with
`deadline=None` and nothing wrote an event while it waited.

Negative case, second site: bounding `_settle` left every *inline* read in
`MirrorRunner.step` unbounded, so five runs on 2026-10-23 15:33-16:32
(`packaged-mirror-20261023-153338` … `-163257`) sat 380 s in the settle read after a
`RESUME_DIALOG` click and were ended by the watchdog with no cause in the journal. The
same fix applied to one of two sites is the defect, not the fix.
"""

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from maalimbus import runner
from maalimbus.runner import FakeDevice, MaaObserver, MirrorRunner


def _patch_observe(monkeypatch, record, sha="same"):
    def fake(observer, deadline=None):
        record.append(deadline)
        return {"image_sha256": sha}

    monkeypatch.setattr(runner, "observe", fake)


class _Journal:
    """The smallest journal a run needs: one JSON line per event."""

    def __init__(self, directory):
        self.directory = Path(directory)

    def record(self, event, **details):
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": event, **details}, ensure_ascii=False))
            handle.write("\n")


def _runner(tmp_path, **settings):
    return MirrorRunner(FakeDevice(), settings={"rounds": 1, "interval": 0, **settings},
                        directory=tmp_path)


def test_a_round_without_a_caller_deadline_still_gets_one(monkeypatch):
    record = []
    _patch_observe(monkeypatch, record)
    now = time.monotonic()
    runner._settle(None, {"image_sha256": "same"}, "same", 3, 0, None)
    assert record, "the loop must read at least once"
    for deadline in record:
        assert deadline is not None, "an unbounded re-read is the defect"
        assert deadline <= now + runner.RE_SETTLE_LIMIT_S + 1


def test_a_caller_deadline_is_a_ceiling_and_a_looser_one_is_capped(monkeypatch):
    # D110 made the read ceiling part of the door: a caller asking for 12345 s still gets
    # at most ONE_READ_SECONDS.  The old assertion ("forwarded unchanged") pinned the
    # absence of that cap, so it is the assertion that was stale, not the rule.
    record = []
    _patch_observe(monkeypatch, record)
    now = time.monotonic()
    runner._settle(None, {"image_sha256": "same"}, "same", 2, 0, 12345.0)
    assert record and all(d <= now + runner.ONE_READ_SECONDS + 1 for d in record)
    record.clear()
    runner._settle(None, {"image_sha256": "same"}, "same", 2, 0, now + 5.0)
    assert record and all(d <= now + 5.0 + 1 for d in record)


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


# -- the runner's own reads: one rule, every call site ---------------------

def test_a_runner_read_is_bounded_without_a_caller_deadline(tmp_path, monkeypatch):
    """`_observe` is the single door every read goes through, so it takes the bound.

    The five 2026-10-23 runs read through `MirrorRunner.step`'s own settle loop, not
    through `_settle`; a bound on the helper alone could not reach them.
    """
    seen = []
    _patch_observe(monkeypatch, seen)
    now = time.monotonic()
    _runner(tmp_path)._observe()
    assert seen and seen[0] is not None, "an unbounded read is the defect"
    assert seen[0] <= now + runner.ONE_READ_SECONDS + 1


def test_a_tighter_run_deadline_still_wins(tmp_path, monkeypatch):
    """The read may not outlive the run either: the bound is a min, not a replacement."""
    seen = []
    _patch_observe(monkeypatch, seen)
    loop = _runner(tmp_path)
    loop.deadline = time.monotonic() + 5
    loop._observe()
    assert seen[0] <= loop.deadline + 0.1 or seen[0] < time.monotonic() + runner.ONE_READ_SECONDS


def test_the_read_in_flight_is_visible_to_the_watchdog(tmp_path, monkeypatch):
    """The watchdog runs beside the call, so it can only report what memory holds."""
    loop = _runner(tmp_path)
    during = []

    def fake(observer, deadline=None):
        during.append(loop._in_flight_report())
        return {"image_sha256": "same"}

    monkeypatch.setattr(runner, "observe", fake)
    loop.state["page"] = "RESUME_DIALOG"
    loop._observe(phase="settle")
    inside, = during
    assert inside["phase"] == "settle" and inside["page"] == "RESUME_DIALOG"
    assert inside["in_flight"] is True and inside["limit_seconds"] > 0
    after = loop._in_flight_report()
    assert "in_flight" not in after, "a finished read is not a wedge"
    assert after["lasted_seconds"] >= 0


def test_a_wedged_node_read_returns_instead_of_spending_the_run(tmp_path):
    """The live wedge itself: one pipeline node that never finishes.

    `packaged-mirror-20261023-153338` … `-163257` each spent 380 s here. With a
    bounded deadline the same node returns, the observer refuses to hand back a page
    it did not read, and the run ends on a stated reason instead of on silence.
    """

    class NeverDone:
        done = False
        succeeded = False

    class Finished:
        done = True
        succeeded = False

    class Tasker:
        def post_task(self, name):
            return NeverDone()

        def post_stop(self):
            return Finished()

    context = SimpleNamespace(tasker=Tasker(), directory=tmp_path, run=None, journal=None)
    observer = MaaObserver(context, tmp_path, read_tries=1)
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="observation node recorded no page"):
        observer.observe(deadline=time.monotonic() + 0.3)
    assert time.monotonic() - started < 3.0, "a wedged read must return, not wait"


def test_a_wedged_read_ends_its_run_instead_of_eating_the_budget(tmp_path, monkeypatch):
    """Integration: the loop retries a failed read a bounded number of times, then ends.

    D59 changed the ending, not the boundedness: before it the *first* failed read ended
    the run (`the_task_raised_before_the_next_input`), so one 30 s hiccup forfeited the
    rest of a 420 s window.  The read is still bounded, the retries are counted, and the
    ending now carries the read's own reason.
    """

    class NeverDone:
        done = False
        succeeded = False

    class Finished:
        done = True
        succeeded = False

    class Tasker:
        def post_task(self, name):
            return NeverDone()

        def post_stop(self):
            return Finished()

    monkeypatch.setattr(runner, "ONE_READ_SECONDS", 0.2)
    context = SimpleNamespace(tasker=Tasker(), directory=tmp_path, run=None, journal=None)
    loop = MirrorRunner(FakeDevice(), settings={"rounds": 1, "interval": 0, "steps": 1,
                                                "stall_seconds": 0, "progress_seconds": 0},
                        directory=tmp_path, journal=_Journal(tmp_path),
                        observer=MaaObserver(context, tmp_path, read_tries=1))
    started = time.monotonic()
    result = loop.run(steps=1, interval=0, round_limit=1)
    spent = time.monotonic() - started
    assert result["passed"] is False
    assert loop.state["session_ended"] == runner.ReadNeverReturned.reason
    assert spent < 10.0, f"one wedged read may not spend the run (took {spent:.1f}s)"
    failures = [row for row in runner.events(tmp_path, "loop_read_failed")]
    assert [row["failures"] for row in failures] == [1, 2, 3], failures
    ended = runner.events(tmp_path, "mirror_session_ended")
    assert ended and "no page for this frame" in ended[-1]["error"]



# -- the bound is the door's, not the caller's ---------------------------------


class _NeverDone:
    done = False
    succeeded = False


class _Finished:
    done = True
    succeeded = False


class _WedgedTasker:
    """A tasker whose node never finishes, and which remembers what it was asked."""

    def __init__(self):
        self.posted = []

    def post_task(self, name):
        self.posted.append(name)
        return _NeverDone()

    def post_stop(self):
        return _Finished()


def _direct_reader(tmp_path, tasker, *, read_tries=1):
    context = SimpleNamespace(tasker=tasker, directory=tmp_path, run=None, journal=None)
    return MaaObserver(context, tmp_path, read_tries=read_tries)


def test_a_read_is_bounded_with_no_runner_and_no_deadline(tmp_path, monkeypatch):
    """The invariant may not depend on `MirrorRunner._observe` having been called.

    `Tools/lux_task.py` and `tools/reward_task.py` read through `runner.observe`, and
    the window layer reads through `MaaObserver.observe` directly: a clamp that lives
    in the runner's private door leaves every one of those open.
    """

    monkeypatch.setattr(runner, "ONE_READ_SECONDS", 0.2)
    tasker = _WedgedTasker()
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="observation node recorded no page"):
        _direct_reader(tmp_path, tasker).observe(deadline=None)
    spent = time.monotonic() - started
    assert spent < 3.0, f"a read with no deadline must still end (took {spent:.1f}s)"
    assert tasker.posted == ["WindowMapObserve"]


def test_a_retry_gets_its_own_window_and_not_the_whole_call(tmp_path, monkeypatch):
    """Two attempts cost two windows, so a retry cannot silently double the bound."""

    monkeypatch.setattr(runner, "ONE_READ_SECONDS", 0.2)
    tasker = _WedgedTasker()
    started = time.monotonic()
    with pytest.raises(RuntimeError):
        _direct_reader(tmp_path, tasker, read_tries=2).observe(deadline=None)
    spent = time.monotonic() - started
    assert len(tasker.posted) == 2, "the second attempt must still happen"
    assert spent < 1.2, f"two attempts may not cost more than two windows (took {spent:.1f}s)"


def test_a_tighter_caller_window_still_wins(tmp_path, monkeypatch):
    """The door clamps; it never extends a caller that already asked for less."""

    monkeypatch.setattr(runner, "ONE_READ_SECONDS", 30.0)
    tasker = _WedgedTasker()
    started = time.monotonic()
    with pytest.raises(RuntimeError):
        _direct_reader(tmp_path, tasker).observe(deadline=time.monotonic() + 0.2)
    spent = time.monotonic() - started
    assert spent < 1.5, f"the caller's 0.2 s window has to win (took {spent:.1f}s)"


def test_bounded_read_is_a_ceiling_and_never_an_extension():
    """The formula itself, with a clock that cannot drift in a test."""

    now = 100.0
    clock = lambda: now  # noqa: E731 - a fixed clock is the point
    assert runner.bounded_read(None, clock=clock) == now + runner.ONE_READ_SECONDS
    assert runner.bounded_read(now + 5, clock=clock) == now + 5
    assert runner.bounded_read(now + 10_000, clock=clock) == now + runner.ONE_READ_SECONDS
    assert runner.bounded_read(None, limit=1.0, clock=clock) == now + 1.0
    assert runner.bounded_read(now + 0.5, limit=1.0, clock=clock) == now + 0.5


def test_the_door_hands_every_observer_a_bounded_window(tmp_path):
    """Any `Observer` implementation, not only the Maa one, receives the ceiling."""

    seen = []

    class Reader:
        directory = tmp_path

        def observe(self, *, deadline=None):
            seen.append(deadline)
            return {"scene": "MAP"}

    now = time.monotonic()
    assert runner.observe(Reader())["scene"] == "MAP"
    assert seen[0] is not None, "an unbounded read reached the observer"
    assert seen[0] <= now + runner.ONE_READ_SECONDS + 1
    runner.observe(Reader(), now + 0.5)
    assert seen[1] <= now + 0.6, "the caller's tighter window must pass through"
