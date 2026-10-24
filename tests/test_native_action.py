"""A node action is bounded and visible, the way a page read is.

Negative case, action door: after `dea7028` and `92be12e` bounded every read,
`src/maalimbus/runner.py` still called `run_node(self.tasker, plan['node'],
self.deadline)` -- the whole run's budget as the window for one action.  A node that
never came back could therefore sit inside the budget exactly like the read that
motivated D37, and no watchdog could name it: only reads stamped
`artifacts['reading']`, so a run wedged inside `run_node` reported `in_flight: false`
and read as if nothing had been in flight at all.

Positive case: the one plan that sends an action is DRIVE's `MirrorDrive`
(`window.PAGE_NODES`), so this is the door every node action passes.
"""

import json
import time
from pathlib import Path

import pytest

from maalimbus import runner
from maalimbus.runner import ActionNeverReturned, FakeDevice, MirrorRunner, bounded_action

NODE = "MirrorDrive"


class _Journal:
    """The smallest journal a run needs: one JSON line per event."""

    def __init__(self, directory):
        self.directory = Path(directory)

    def record(self, event, **details):
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": event, **details}, ensure_ascii=False))
            handle.write("\n")


def _events(tmp_path, name):
    path = Path(tmp_path) / "events.jsonl"
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    return [row for row in rows if row.get("event") == name]


class _NeverDone:
    done = False
    succeeded = False


class _Finished:
    done = True
    succeeded = False


class _Succeeded:
    done = True
    succeeded = True


class _Tasker:
    """A tasker whose node never finishes, and which remembers what it was asked."""

    def __init__(self, job=None, watch=None):
        self.job = _NeverDone() if job is None else job
        self.posted = []
        self.watch = watch

    def post_task(self, name):
        self.posted.append(name)
        if self.watch is not None:
            self.watch.append(name)
        return self.job

    def post_stop(self):
        return _Finished()


def _runner(tmp_path, tasker=None, **settings):
    """A loop whose device carries the tasker, which is where `MirrorRunner` reads it."""
    device = FakeDevice()
    if tasker is not None:
        device.tasker = tasker
    return MirrorRunner(device, settings={"rounds": 1, "interval": 0, **settings},
                        directory=tmp_path, journal=_Journal(tmp_path))


# -- the bound ------------------------------------------------------------------


def test_the_action_bound_is_a_ceiling_and_never_an_extension():
    clock = lambda: 100.0  # noqa: E731 - a fixed clock is the point
    assert bounded_action(None, clock=clock) == 100.0 + runner.ONE_ACTION_SECONDS
    assert bounded_action(105.0, clock=clock) == 105.0
    assert bounded_action(10_000.0, clock=clock) == 100.0 + runner.ONE_ACTION_SECONDS
    assert bounded_action(None, limit=1, clock=clock) == 101.0


def test_a_wedged_action_returns_instead_of_spending_the_run(tmp_path, monkeypatch):
    """The action door's own wedge: one node that never finishes."""
    monkeypatch.setattr(runner, "ONE_ACTION_SECONDS", 0.2)
    tasker = _Tasker()
    loop = _runner(tmp_path, tasker=tasker)
    started = time.monotonic()
    with pytest.raises(ActionNeverReturned) as caught:
        loop._act(NODE)
    spent = time.monotonic() - started
    assert spent < 3.0, f"a wedged action must return, not wait (took {spent:.1f}s)"
    assert caught.value.reason == "the_action_node_did_not_finish_inside_its_window"
    assert tasker.posted == [NODE], "the action was posted once, then bounded"
    acting = loop.artifacts["acting"]
    assert acting["node"] == NODE and acting["lasted_seconds"] >= 0


def test_a_node_plan_without_a_tasker_is_refused_before_anything_is_posted(tmp_path):
    loop = _runner(tmp_path)
    with pytest.raises(RuntimeError, match="a node plan needs a Maa tasker"):
        loop._act(NODE)


# -- the record -----------------------------------------------------------------


def test_the_watchdog_can_name_the_action_it_is_waiting_on(tmp_path):
    """The watchdog runs beside the call, so it can only report what memory holds."""
    during = []
    loop = None

    class Watching(_Tasker):
        def post_task(self, name):
            during.append(loop._in_flight_report())
            return super().post_task(name)

    loop = _runner(tmp_path, tasker=Watching(job=_Succeeded()))
    loop.state["page"] = "DRIVE"
    loop._act(NODE)
    inside, = during
    assert inside["phase"] == "node_action"
    assert inside["node"] == NODE
    assert inside["page"] == "DRIVE"
    assert inside["in_flight"] is True
    assert inside["limit_seconds"] > 0
    after = loop._in_flight_report()
    assert "in_flight" not in after, "an action that came back is not a wedge"
    assert after["lasted_seconds"] >= 0 and after["node"] == NODE


def test_the_later_of_the_two_stamps_is_the_one_reported(tmp_path):
    """A read and an action leave different stamps; the loop reports the current one."""
    loop = _runner(tmp_path)
    loop.artifacts["reading"] = {"phase": "settle", "since": time.monotonic() - 30,
                                 "page": "MAP", "limit_seconds": 30,
                                 "lasted_seconds": 2.0}
    loop.artifacts["acting"] = {"phase": "node_action", "since": time.monotonic() - 1,
                                "node": NODE, "page": "DRIVE", "limit_seconds": 60}
    report = loop._in_flight_report()
    assert report["phase"] == "node_action" and report["in_flight"] is True


def test_an_action_that_came_back_unconfirmed_ends_the_run(tmp_path):
    """A node that answers "no" means Maa tore the task down; no input may follow (D72).

    Live evidence twice on 2026-10-23: packaged-mirror-20261023-221109 posted a click at
    (966, 591) and -223237 one at (958, 595) right after `node_action_unconfirmed`; both
    reached the framework as `controller not found [controller_id=]` and both runs then sat
    until their budget killed them.  The note is kept, and the ending is now named.
    """
    loop = _runner(tmp_path, tasker=_Tasker(job=_Finished()))
    with pytest.raises(runner.ActionNodeFailed, match="reported stopped"):
        loop._act(NODE)
    noted = _events(tmp_path, "node_action_unconfirmed")
    assert noted and noted[-1]["node"] == NODE
    assert noted[-1]["verdict"] == "stopped"
    assert loop.device.ended == runner.ActionNodeFailed.reason
    with pytest.raises(RuntimeError, match="the session ended"):
        loop.device.click(10, 20)


def test_a_wedged_action_ends_its_run_with_its_own_reason(tmp_path, monkeypatch):
    """Integration: the loop ends on the action's reason instead of on silence."""
    monkeypatch.setattr(runner, "ONE_ACTION_SECONDS", 0.2)
    monkeypatch.setattr(runner, "observe",
                        lambda observer, deadline=None: {"scene": "DRIVE",
                                                         "image_sha256": "same",
                                                         "size": [1920, 1080],
                                                         "ocr": []})
    loop = _runner(tmp_path, tasker=_Tasker(), steps=1, stall_seconds=0,
                   progress_seconds=0)
    started = time.monotonic()
    result = loop.run(steps=1, interval=0, round_limit=1)
    spent = time.monotonic() - started
    assert result["passed"] is False
    assert loop.state["session_ended"] == "the_action_node_did_not_finish_inside_its_window"
    assert spent < 10.0, f"one wedged action may not spend the run (took {spent:.1f}s)"
    ended = runner.events(tmp_path, "mirror_session_ended")
    assert ended and "did not come back" in ended[-1]["error"]
