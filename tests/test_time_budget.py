"""Where the seconds went, and what the journal cannot explain (D66).

`mean_seconds` said how long a run lasted.  These tests pin the next question: the gap
from a row to the next stamped row is the time that row cost, a gap beyond the cap is
excluded and *reported*, and the group shares divide the attributed time -- not the
total, because the part the journal cannot explain must not be handed to the lines that
were left.
"""

import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'src'))
sys.path.insert(0, str(HERE / 'tools'))

from maalimbus import run_metrics  # noqa: E402


def _row(event, utc, **fields):
    return {'event': event, 'utc': utc, **fields}


def test_the_gap_belongs_to_the_row_that_cost_it():
    rows = [
        _row('loop_heartbeat', '2026-10-23T10:00:00+00:00'),
        _row('map_observed', '2026-10-23T10:00:05+00:00', scene='MAP'),
        _row('window_intent', '2026-10-23T10:00:07+00:00', page='MAP'),
    ]
    budget = run_metrics.time_budget(rows)
    # The last row is not attributed anything: there is no next stamp to subtract, and a
    # row whose cost nobody observed is not a row that cost zero.
    assert budget['events']['loop_heartbeat']['seconds'] == 5.0
    assert budget['events']['map_observed']['seconds'] == 2.0
    assert 'window_intent' not in budget['events']
    assert budget['total_seconds'] == 7.0
    assert budget['attributed_seconds'] == 7.0


def test_a_gap_beyond_the_cap_is_excluded_and_reported():
    rows = [
        _row('map_observed', '2026-10-23T10:00:00+00:00'),
        _row('map_observed', '2026-10-23T10:05:00+00:00'),
    ]
    budget = run_metrics.time_budget(rows)
    assert budget['capped_gaps'] == 1
    assert budget['attributed_seconds'] == 0.0
    assert budget['unattributed_seconds'] == 300.0
    assert budget['events'] == {}
    # The counter-example: the same two rows inside the cap are attributed.
    rows[1]['utc'] = '2026-10-23T10:00:30+00:00'
    assert run_metrics.time_budget(rows)['attributed_seconds'] == 30.0


def test_the_cap_is_a_parameter_so_a_short_step_is_not_excluded():
    rows = [
        _row('map_observed', '2026-10-23T10:00:00+00:00'),
        _row('map_observed', '2026-10-23T10:05:00+00:00'),
    ]
    assert run_metrics.time_budget(rows, cap=600)['attributed_seconds'] == 300.0


def test_every_event_lands_in_exactly_one_group():
    declared = [event for _, events in run_metrics.TIME_GROUPS for event in events]
    assert len(declared) == len(set(declared))
    assert run_metrics.group_of('map_observed') == 'reads'
    assert run_metrics.group_of('window_unknown_wait') == 'waits'
    assert run_metrics.group_of('window_recovery') == 'recovery'
    # An event nobody grouped is reported as `other`, not dropped.
    assert run_metrics.group_of('a_brand_new_event') == run_metrics.OTHER_GROUP


def test_the_group_seconds_add_up_to_the_attributed_seconds():
    rows = [
        _row('map_observed', '2026-10-23T10:00:00+00:00'),
        _row('window_unknown_wait', '2026-10-23T10:00:06+00:00'),
        _row('window_recovery', '2026-10-23T10:00:15+00:00'),
        _row('a_brand_new_event', '2026-10-23T10:00:17+00:00'),
    ]
    budget = run_metrics.time_budget(rows)
    total = sum(entry['seconds'] for entry in budget['groups'].values())
    assert total == budget['attributed_seconds'] == 17.0
    assert set(budget['groups']) == {'reads', 'waits', 'recovery'}
    assert budget['groups']['waits']['events'] == ['window_unknown_wait']


def test_an_event_nobody_grouped_is_kept_under_other():
    rows = [
        _row('a_brand_new_event', '2026-10-23T10:00:00+00:00'),
        _row('a_brand_new_event', '2026-10-23T10:00:03+00:00'),
    ]
    budget = run_metrics.time_budget(rows)
    assert set(budget['groups']) == {run_metrics.OTHER_GROUP}
    assert budget['groups'][run_metrics.OTHER_GROUP]['seconds'] == 3.0


def test_an_offset_and_a_zulu_stamp_are_the_same_clock():
    rows = [
        _row('map_observed', '2026-10-23T10:00:00Z'),
        _row('map_observed', '2026-10-23T12:00:05+02:00'),
    ]
    assert run_metrics.time_budget(rows)['attributed_seconds'] == 5.0


def test_a_row_without_a_parseable_stamp_is_skipped_not_guessed():
    rows = [
        _row('map_observed', '2026-10-23T10:00:00+00:00'),
        _row('map_observed', 'not a time'),
        _row('window_recovery', '2026-10-23T10:00:04+00:00'),
    ]
    budget = run_metrics.time_budget(rows)
    assert budget['attributed_seconds'] == 4.0
    assert set(budget['events']) == {'map_observed'}


def test_one_stamp_is_not_a_budget():
    budget = run_metrics.time_budget([_row('map_observed', '2026-10-23T10:00:00+00:00')])
    assert budget['total_seconds'] is None
    assert budget['unattributed_seconds'] is None
    assert budget['attributed_seconds'] == 0.0


def test_the_mean_is_the_seconds_over_the_rows():
    rows = [
        _row('map_observed', '2026-10-23T10:00:00+00:00'),
        _row('map_observed', '2026-10-23T10:00:02+00:00'),
        _row('map_observed', '2026-10-23T10:00:06+00:00'),
    ]
    budget = run_metrics.time_budget(rows)
    assert budget['events']['map_observed'] == {'seconds': 6.0, 'n': 2, 'mean': 3.0,
                                                'group': 'reads'}


def test_the_portfolio_says_which_and_how_many_runs_it_could_measure():
    first = run_metrics.time_budget([
        _row('map_observed', '2026-10-23T10:00:00+00:00'),
        _row('window_unknown_wait', '2026-10-23T10:00:09+00:00'),
    ])
    second = run_metrics.time_budget([_row('map_observed', '2026-10-23T11:00:00+00:00')])
    report = run_metrics.time_portfolio([first, second])
    assert report['value']['attributed_seconds'] == 9.0
    # The 9 s gap belongs to the read that preceded the wait, not to the wait.
    assert report['value']['groups']['reads']['share'] == 1.0
    assert report['value']['per_event']['map_observed']['mean'] == 9.0
    assert '1 of 2 runs carry two or more timestamps' in report['basis']


def test_a_corpus_with_no_measurement_says_not_measured():
    report = run_metrics.time_portfolio([run_metrics.time_budget([])])
    assert report['value'] is None
    assert 'no time was attributed' in report['note']


def test_the_tool_prints_the_groups_and_returns_zero(capsys):
    import audit_time
    assert audit_time.main([]) == 0
    printed = capsys.readouterr().out
    assert 'attributed seconds' in printed
    assert 'the lines that own the time:' in printed
    assert 'basis:' in printed


def test_the_tool_says_so_when_there_is_nothing_to_read(tmp_path, capsys):
    import audit_time
    (tmp_path / 'empty').mkdir()
    assert audit_time.main(['--root', str(tmp_path)]) == 2
    assert 'no run wrote a journal' in capsys.readouterr().out


def test_the_portfolio_carries_a_time_budget_next_to_the_measures():
    portfolio = run_metrics.portfolio([])
    assert set(portfolio) == {'runs', 'measures', 'time', 'reads', 'split'}
    assert portfolio['time']['value'] is None
    assert 'no time was attributed' in portfolio['time']['note']
