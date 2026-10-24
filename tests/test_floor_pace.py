"""How long a floor takes, against the player's own requirement (D95).

The requirement stated on 2026-10-24 is one floor per ten minutes, i.e. a five-floor
exploration in fifty. `clear_rate` cannot answer it (no run has cleared five floors)
and `floor_progress` answers a different question (how far a run got), so the pace is
its own measure -- and it has two traps the tests below pin:

* the journal writes the floor as a **string** (`'2'`, `'3'`); a numeric type check
  silently drops every reading, which is exactly what the first version did (five runs
  walked two floors and all five reported no pace);
* a floor label that moves within seconds is a label read twice, not a floor walked.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import run_metrics  # noqa: E402


def _row(event, utc, **fields):
    return dict(event=event, utc=utc, **fields)


def _seen(floor, utc):
    return _row('map_observed', utc, scene='MAP', floor=floor)


def test_a_floor_walked_over_four_hundred_seconds_is_four_hundred_seconds():
    rows = [_row('mirror_loop_started', '2026-10-24T10:00:00+00:00'),
            _seen('2', '2026-10-24T10:01:00+00:00'),
            _seen('3', '2026-10-24T10:07:40+00:00')]
    pace = run_metrics.floor_pace(rows)
    assert pace['per_floor'] == 400.0
    assert pace['floors'] == 1
    assert (pace['from_floor'], pace['to_floor']) == (2, 3)


def test_the_floor_the_journal_writes_is_a_string():
    """The regression: a number-only check reported 'no run gained a floor'."""
    rows = [_seen('2', '2026-10-24T10:00:00+00:00'),
            _seen('3', '2026-10-24T10:10:00+00:00')]
    assert run_metrics.floor_pace(rows)['per_floor'] == 600.0
    assert run_metrics._floor_of('3') == 3
    assert run_metrics._floor_of(3) == 3
    assert run_metrics._floor_of(' 2 ') == 2
    assert run_metrics._floor_of('two') is None
    assert run_metrics._floor_of(True) is None
    assert run_metrics._floor_of(None) is None


def test_two_floors_apart_are_averaged_per_floor():
    rows = [_seen('1', '2026-10-24T10:00:00+00:00'),
            _seen('3', '2026-10-24T10:20:00+00:00')]
    pace = run_metrics.floor_pace(rows)
    assert pace['floors'] == 2
    assert pace['per_floor'] == 600.0


def test_a_label_that_repeats_within_seconds_is_not_a_floor():
    """Measured: five runs showed two floors 5-19 s apart; that is one floor read twice."""
    rows = [_seen('2', '2026-10-24T10:00:00+00:00'),
            _seen('3', '2026-10-24T10:00:05+00:00')]
    assert run_metrics.floor_pace(rows) is None


def test_one_floor_has_no_pace():
    rows = [_seen('2', '2026-10-24T10:00:00+00:00'),
            _seen('2', '2026-10-24T10:05:00+00:00')]
    assert run_metrics.floor_pace(rows) is None


def test_a_floor_that_goes_backwards_is_not_a_gain():
    rows = [_seen('3', '2026-10-24T10:00:00+00:00'),
            _seen('2', '2026-10-24T10:05:00+00:00')]
    assert run_metrics.floor_pace(rows) is None


def test_a_reading_without_a_stamp_is_not_a_reading():
    rows = [_seen('2', '2026-10-24T10:00:00+00:00'),
            {'event': 'map_observed', 'floor': '3'}]
    assert run_metrics.floor_pace(rows) is None


def test_the_measure_names_the_target_the_player_stated():
    fast = [_seen('1', '2026-10-24T10:00:00+00:00'), _seen('2', '2026-10-24T10:05:00+00:00')]
    slow = [_seen('1', '2026-10-24T10:00:00+00:00'), _seen('2', '2026-10-24T11:00:00+00:00')]
    measure = run_metrics.metrics([run_metrics.efficiency(fast), run_metrics.efficiency(slow)])
    figure = measure['seconds_per_floor']
    assert figure['value'] == 1950.0
    assert 'target 600 s per floor' in figure['basis']
    assert '1 of 2 at or under it' in figure['basis']


def test_a_corpus_that_never_walked_a_floor_says_so_instead_of_zero():
    one = [_seen('2', '2026-10-24T10:00:00+00:00')]
    figure = run_metrics.metrics([run_metrics.efficiency(one)])['seconds_per_floor']
    assert figure['value'] is None
    assert 'no run gained a floor' in figure['basis']
    assert 'not' in (figure['note'] or '') or 'no retained run' in (figure['note'] or '')


def test_the_measure_list_carries_it_next_to_the_other_floors():
    assert 'seconds_per_floor' in run_metrics.MEASURES
    assert run_metrics.MEASURES.index('seconds_per_floor') == run_metrics.MEASURES.index('floor_progress') + 1
    assert run_metrics.TARGET_SECONDS_PER_FLOOR == 600.0
    assert run_metrics.MIN_FLOOR_SECONDS >= 30.0


def test_the_tool_prints_the_pace():
    import subprocess
    done = subprocess.run([sys.executable, str(ROOT / 'tools' / 'audit_efficiency.py')],
                          capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    assert done.returncode == 0, done.stderr[-400:]
    assert 'seconds_per_floor' in done.stdout
