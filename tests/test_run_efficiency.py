"""D61 and D67: the six figures phase 6 asks for, and the difference between 0 and None.

A run that was not measured must report `None`, not `0` -- this session published two
wrong conclusions by letting a default stand in for a measurement (D50's census that lost
ten runs, D56's "28 unjudgeable words" that were all judged by a dismissal).  So the
tests here are about boundaries: one timestamp is not a duration, a corpus that never
bought anything is not a corpus where nothing went wrong -- and, since D67, a heartbeat is
not a step.  The heartbeat was added on 2026-10-23 for runs that died with no cause, so an
archive spanning older builds has far fewer heartbeats than steps, and `reads_per_step`
published 34.2 for a corpus whose real figure is 9.73.
"""

import importlib.util
import json
import pathlib

import pytest

from maalimbus import run_metrics

REPO = pathlib.Path(__file__).resolve().parents[1]


def _row(event, utc=None, **fields):
    row = {'event': event}
    if utc is not None:
        row['utc'] = utc
    row.update(fields)
    return row


def _journal(directory, rows):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'events.jsonl'
    path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')
    return directory


def _stamp(second):
    """An ISO stamp `second` seconds after 20:00:00.  Built from minutes because
    `20:00:90` is not a time -- the first version of this helper made the third timestamp
    unparseable and the test read a shorter duration."""
    return f'2026-10-23T20:{second // 60:02d}:{second % 60:02d}.000000+00:00'


def test_a_run_with_two_timestamps_has_a_duration():
    rows = [_row('loop_heartbeat', _stamp(0)),
            _row('map_observed', _stamp(90), scene='MAP', floor=1)]
    assert run_metrics.efficiency(rows)['seconds'] == 90.0


def test_one_timestamp_is_not_a_duration():
    rows = [_row('loop_heartbeat', _stamp(0))]
    assert run_metrics.efficiency(rows)['seconds'] is None


def test_reads_count_every_frame_that_named_a_page():
    rows = [_row('loop_heartbeat', _stamp(0)),
            _row('map_observed', _stamp(1), scene='MAP', floor=1),
            _row('scene_mismatch', _stamp(2), expected='MAP', scene='RESUME_DIALOG'),
            _row('map_observed', _stamp(3), scene='MAP', floor=1),
            _row('mirror_loop_stopped', _stamp(4), steps=1, stop_path='agent_loop')]
    measured = run_metrics.efficiency(rows)
    # D191: a scene_mismatch is a guard node probing, not a read the loop spent.
    assert measured['reads'] == 2
    assert measured['probes'] == 1
    assert measured['steps'] == 1
    assert measured['heartbeats'] == 1
    assert measured['reads_per_step'] == 2.0


def test_a_heartbeat_is_not_a_step():
    """The rate the corpus publishes is a rate over steps.  A run that documented three
    steps but declared no step count has no rate -- not a rate with 3 in the denominator."""
    rows = [_row('loop_heartbeat', _stamp(0)),
            _row('loop_heartbeat', _stamp(1)),
            _row('loop_heartbeat', _stamp(2)),
            _row('map_observed', _stamp(3), floor=1)]
    measured = run_metrics.efficiency(rows)
    assert measured['heartbeats'] == 3
    assert measured['steps'] is None
    assert measured['reads_per_step'] is None


def test_the_step_count_the_loop_declares_is_the_denominator():
    rows = [_row('loop_heartbeat', _stamp(0))]
    rows += [_row('map_observed', _stamp(i), floor=1) for i in range(1, 11)]
    rows += [_row('mirror_loop_stopped', _stamp(11), steps=5, stop_path='agent_loop')]
    measured = run_metrics.efficiency(rows)
    assert measured['reads'] == 10
    assert measured['steps'] == 5
    assert measured['reads_per_step'] == 2.0


def test_five_floors_is_an_exploration_and_four_is_not():
    five = [_row('map_observed', _stamp(n), floor=n) for n in range(1, 6)]
    four = [_row('map_observed', _stamp(n), floor=n) for n in range(1, 5)]
    assert run_metrics.efficiency(five)['explored'] is True
    assert run_metrics.efficiency(four)['explored'] is False
    assert run_metrics.efficiency(four)['reached_floor'] == 4


def test_an_unconfirmed_purchase_is_the_risk_figure():
    rows = [_row('shop_purchase_sent', _stamp(1)), _row('shop_purchase_sent', _stamp(2)),
            _row('shop_purchase_confirmed', _stamp(3))]
    assert run_metrics.efficiency(rows)['unconfirmed_purchases'] == 1


def test_a_run_that_bought_nothing_is_not_a_zero_risk_claim():
    assert run_metrics.efficiency([_row('loop_heartbeat', _stamp(0))])[
        'unconfirmed_purchases'] is None


def test_a_confirmed_purchase_in_another_run_still_reports_zero():
    runs = [{'run': 'a', **run_metrics.efficiency(
        [_row('shop_purchase_sent', _stamp(1)), _row('shop_purchase_confirmed', _stamp(2))])}]
    row = run_metrics.metrics(runs)['unconfirmed_purchases']
    assert row['value'] == 0
    assert 'every one was confirmed' in row['basis']
    assert 'absent, not measured' not in row['note']


def test_a_corpus_that_never_bought_says_so():
    runs = [{'run': 'a', **run_metrics.efficiency([_row('loop_heartbeat', _stamp(0))])}]
    row = run_metrics.metrics(runs)['unconfirmed_purchases']
    assert row['value'] == 0
    assert 'no run of 1 wrote a purchase event' in row['basis']
    assert 'not measured' in row['note']


def test_every_measure_has_a_value_and_a_basis():
    runs = [{'run': 'a', **run_metrics.efficiency([_row('loop_heartbeat', _stamp(0))])}]
    measured = run_metrics.metrics(runs)
    assert set(measured) == set(run_metrics.MEASURES)
    for name, row in measured.items():
        assert row['basis'], name
        if row['value'] is None:
            assert row['note'], name


def test_a_single_run_that_reached_no_floor_is_not_a_rate_of_zero():
    runs = [{'run': 'a', **run_metrics.efficiency([_row('loop_heartbeat', _stamp(0))])}]
    assert run_metrics.metrics(runs)['clear_rate']['value'] == 0.0


def test_the_portfolio_skips_a_directory_with_no_journal(tmp_path):
    empty = tmp_path / 'packaged-mirror-1'
    empty.mkdir()
    measured = run_metrics.portfolio([empty])
    assert measured['runs'] == []
    assert measured['measures']['mean_seconds']['value'] is None


def test_the_portfolio_measures_the_runs_it_can_read(tmp_path):
    _journal(tmp_path / 'packaged-mirror-1', [
        _row('loop_heartbeat', _stamp(0)),
        _row('map_observed', _stamp(30), floor=1),
        _row('mirror_loop_stopped', _stamp(60), stop_path='no_progress_watchdog', steps=1,
             reason='the_run_kept_observing_without_writing_anything')])
    measured = run_metrics.portfolio([tmp_path / 'packaged-mirror-1'])
    assert len(measured['runs']) == 1
    assert measured['runs'][0]['seconds'] == 60.0
    assert measured['measures']['mean_seconds']['value'] == 60.0
    assert measured['measures']['reads_per_step']['value'] == 1.0
    assert measured['measures']['no_progress_stop_rate']['value'] == 0.0


def test_a_corpus_rate_does_not_mix_heartbeats_with_steps():
    """D67: the numerator and the denominator have to come from the same runs.  An older
    run that wrote heartbeats but declared no step count must not contribute reads to a
    rate whose denominator is the newer runs' steps."""
    declared = {'run': 'declared', **run_metrics.efficiency([
        _row('map_observed', _stamp(0), floor=1),
        _row('map_observed', _stamp(1), floor=1),
        _row('mirror_loop_stopped', _stamp(2), steps=2, stop_path='agent_loop')])}
    older = {'run': 'older', **run_metrics.efficiency([
        _row('loop_heartbeat', _stamp(0)),
        _row('map_observed', _stamp(1), floor=1),
        _row('map_observed', _stamp(2), floor=1),
        _row('map_observed', _stamp(3), floor=1)])}
    figure = run_metrics.metrics([declared, older])['reads_per_step']
    assert figure['value'] == 1.0
    assert '2 reads over 2 steps' in figure['basis']
    assert '1 of 2 runs' in figure['basis']
    assert 'heartbeat is not a step' in figure['note']


def _tool():
    path = REPO / 'tools' / 'audit_efficiency.py'
    spec = importlib.util.spec_from_file_location('audit_efficiency', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_tool_prints_one_line_per_measure(tmp_path, capsys):
    _journal(tmp_path / 'packaged-mirror-1', [
        _row('loop_heartbeat', _stamp(0)),
        _row('map_observed', _stamp(10), floor=1),
        _row('loop_heartbeat', _stamp(20))])
    exit_code = _tool().main([str(tmp_path / 'packaged-mirror-1')])
    out = capsys.readouterr().out
    assert exit_code == 0
    for name in run_metrics.MEASURES:
        assert name in out, name
    assert 'runs read: 1' in out
    assert 'basis:' in out


def test_the_tool_says_so_when_there_is_nothing_to_read(tmp_path, capsys):
    exit_code = _tool().main([str(tmp_path / 'missing')])
    out = capsys.readouterr().out
    assert exit_code == 2
    assert 'nothing to measure' in out


def test_the_archive_and_the_tool_agree():
    archive = REPO / 'evidence' / 'runtime'
    if not any(archive.glob('packaged-mirror-*/events.jsonl')):
        pytest.skip('no retained archive on this machine')
    report = run_metrics.portfolio()
    assert report['runs'], 'the archive is there but nothing was read'
    assert set(report['measures']) == set(run_metrics.MEASURES)
    kinds = {run['ending']['kind'] for run in report['runs']}
    assert kinds <= set(run_metrics.ENDING_KINDS), kinds
    for run in report['runs']:
        assert (run['seconds'] is None) or run['seconds'] >= 0


def _census_tool():
    path = REPO / 'tools' / 'audit_runs.py'
    spec = importlib.util.spec_from_file_location('audit_runs', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_two_measurement_tools_count_the_same_archive_the_same_way():
    """D50's rule, applied to the efficiency report: one archive, one answer."""
    archive = REPO / 'evidence' / 'runtime'
    if not any(archive.glob('packaged-mirror-*/events.jsonl')):
        pytest.skip('no retained archive on this machine')
    census = _census_tool()
    corpus = run_metrics._archives()
    counts, _paths, failed, _floors = census.census(corpus)
    assert len(failed) == counts['died'] + counts['error']
    report = run_metrics.portfolio()
    measurable = len(report['runs'])
    assert sum(counts.values()) == len(corpus)
    assert counts['no_events'] == len(corpus) - measurable
    measure = report['measures']['no_progress_stop_rate']
    expected = f'{counts["died"]} died + {counts["error"]} errored of {len(corpus)}'
    # D176 publishes the eras in the same basis, so the comparison is a prefix, not equality.
    assert measure['basis'].startswith(expected), (measure['basis'], expected)


# --- D80: a rate over runs nobody gave time to clear is a statement about the budget -----


def _floor_run(floor, *, stop_reason='loop_deadline_exceeded'):
    return [
        _row('map_observed', '2026-10-24T00:00:00Z', scene='MAP'),
        _row('map_observed', '2026-10-24T00:00:10Z', scene='MAP', floor=floor),
        _row('mirror_loop_stopped', '2026-10-24T00:00:20Z', reason=stop_reason,
             stop_path='agent_loop', steps=2),
    ]


def test_a_run_that_ended_on_its_callers_clock_says_so():
    run = run_metrics.efficiency(_floor_run(2))
    assert run['budget_ended'] is True
    other = run_metrics.efficiency(_floor_run(2, stop_reason='page_unreadable_after_waiting'))
    assert other['budget_ended'] is False


def test_the_clear_rate_says_how_much_of_it_was_a_cap():
    report = run_metrics.metrics([run_metrics.efficiency(_floor_run(2))])
    note = report['clear_rate']['note']
    assert '1 of 1 runs were ended by their callers budget' in note
    assert 'D80' in note


def test_the_floor_the_loop_reached_is_its_own_figure():
    runs = [run_metrics.efficiency(_floor_run(2)), run_metrics.efficiency(_floor_run(3))]
    report = run_metrics.metrics(runs)
    assert report['floor_progress']['value'] == 2.5
    assert 'best floor 3' in report['floor_progress']['basis']
    assert '2 of 2 runs reached a floor' in report['floor_progress']['basis']


def test_a_corpus_that_never_walked_a_floor_is_not_a_progress_of_zero():
    rows = [_row('map_observed', '2026-10-24T00:00:00Z', scene='MAP'),
            _row('mirror_loop_stopped', '2026-10-24T00:00:10Z', reason='loop_deadline_exceeded',
                 stop_path='agent_loop', steps=1)]
    report = run_metrics.metrics([run_metrics.efficiency(rows)])
    assert report['floor_progress']['value'] is None
    assert 'none of 1 runs reached a floor' in report['floor_progress']['basis']


def test_the_progress_figure_sits_next_to_the_clear_rate():
    assert run_metrics.MEASURES.index('floor_progress') == (
        run_metrics.MEASURES.index('clear_rate') + 1)


# --- D121: the floor a run *stayed* in -----------------------------------------
def _dwell_rows(seconds, floor='3'):
    return [_row('map_observed', _stamp(0), floor=floor),
            _row('map_observed', _stamp(int(seconds // 2)), floor=floor),
            _row('map_observed', _stamp(int(seconds)), floor=floor)]


def test_the_dwell_of_a_floor_is_the_time_it_was_on_screen():
    dwell = run_metrics.floor_dwell(_dwell_rows(90))
    assert dwell[3]['seconds'] == 90.0
    assert dwell[3]['reads'] == 3
    assert dwell[3]['ended_here'] is True


def test_a_run_that_ends_inside_a_floor_still_reports_its_dwell():
    """The 610 s run of 2026-10-24 reached floor 3 and never left it: pace is None."""
    rows = _dwell_rows(418)
    assert run_metrics.floor_pace(rows) is None
    assert run_metrics.floor_dwell(rows)[3]['seconds'] == 418.0


def test_the_dwell_measure_averages_the_floor_a_run_ended_in():
    short = run_metrics.efficiency(_dwell_rows(100))
    long = run_metrics.efficiency(_dwell_rows(200))
    figure = run_metrics.metrics([short, long])['floor_dwell']
    assert figure['value'] == 150.0
    assert '2 run(s)' in figure['basis']


def test_a_corpus_that_named_no_floor_does_not_claim_a_dwell():
    figure = run_metrics.metrics([run_metrics.efficiency([])])['floor_dwell']
    assert figure['value'] is None
    assert 'no run named a floor' in figure['note']


def test_the_dwell_has_a_name_in_the_measure_list():
    assert 'floor_dwell' in run_metrics.MEASURES


def test_the_death_rate_publishes_how_many_runs_could_name_their_ending():
    dead = run_metrics.efficiency([_row('map_observed', _stamp(1))])
    dead['ending'] = {'kind': 'died', 'path': 'process_died', 'reason': None}
    named = run_metrics.efficiency([_row('map_observed', _stamp(1))])
    named['ending'] = {'kind': 'stop', 'path': 'agent_loop', 'reason': 'x'}
    basis = run_metrics.metrics([dead, named])['no_progress_stop_rate']['basis']
    assert '1 died' in basis and 'of 2' in basis and '1 of 2 could name' in basis
