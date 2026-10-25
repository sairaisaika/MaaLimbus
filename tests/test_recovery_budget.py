"""D166: a recovery attempt is a budget, not a queue of gestures.

The measured case: three `window_recovery` rows of the 2026-10-24 22:07 run held 100.7 of
its 251.5 attributed seconds (33.6 s each), and the last attempt sat silent for 91 s until
the no-progress watch ended the run.  One rung is cheap; the attempt is what costs.
"""
import json
import pathlib

from maalimbus import runner
from maalimbus.runner import FakeDevice, MirrorRunner


class _Journal:
    def __init__(self, directory):
        self.path = pathlib.Path(directory) / 'events.jsonl'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text('', encoding='utf-8')

    def record(self, event, **fields):
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(dict(event=event, **fields), default=str) + '\n')


def _loop(tmp_path):
    journal = _Journal(tmp_path)
    loop = MirrorRunner(FakeDevice(), settings={'rounds': 1, 'interval': 0},
                        directory=tmp_path, journal=journal)
    return loop


ENTRY = {'reason': 'no_candidate_node_observed'}


def test_a_ladder_that_has_used_its_time_spends_no_more_rungs(tmp_path, monkeypatch):
    loop = _loop(tmp_path)
    clock = {'now': 1000.0}
    monkeypatch.setattr(runner.time, 'monotonic', lambda: clock['now'])
    assert loop._recover('MAP', loop.state, dict(ENTRY), {}) is not None
    clock['now'] += runner.RECOVERY_SECONDS + 1.0
    assert loop._recover('MAP', loop.state, dict(ENTRY), {}) is None
    rows = runner.events(tmp_path, 'window_recovery_out_of_time')
    assert rows and rows[0]['rungs'] == 1
    assert rows[0]['spent_seconds'] > runner.RECOVERY_SECONDS


def test_a_fresh_page_starts_a_fresh_attempt(tmp_path, monkeypatch):
    loop = _loop(tmp_path)
    clock = {'now': 1000.0}
    monkeypatch.setattr(runner.time, 'monotonic', lambda: clock['now'])
    assert loop._recover('MAP', loop.state, dict(ENTRY), {}) is not None
    clock['now'] += runner.RECOVERY_SECONDS + 1.0
    assert loop._recover('DEPLOYMENT', loop.state, dict(ENTRY), {}) is not None


def test_an_attempt_inside_its_time_keeps_escalating(tmp_path, monkeypatch):
    loop = _loop(tmp_path)
    clock = {'now': 1000.0}
    monkeypatch.setattr(runner.time, 'monotonic', lambda: clock['now'])
    assert loop._recover('MAP', loop.state, dict(ENTRY), {}) is not None
    clock['now'] += runner.RECOVERY_SECONDS - 1.0
    assert loop._recover('MAP', loop.state, dict(ENTRY), {}) is not None
    assert loop.state['recovery_rung'] == 2


def test_the_attempt_budget_is_far_below_a_run_budget():
    assert 10.0 <= runner.RECOVERY_SECONDS <= 120.0
    assert runner.RECOVERY_SECONDS < runner.DEEP_STEP_SECONDS + runner.ONE_ACTION_SECONDS
