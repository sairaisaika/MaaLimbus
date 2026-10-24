"""D61: the six figures phase 6 asks for, and the difference between 0 and None.

A run that was not measured must report `None`, not `0` -- this session published two
wrong conclusions by letting a default stand in for a measurement (D50's census that lost
ten runs, D56's "28 unjudgeable words" that were all judged by a dismissal).  So the
tests here are about boundaries: one timestamp is not a duration, no heartbeat is not a
rate, a corpus that never bought anything is not a corpus where nothing went wrong.
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


def test_reads_count_every_frame_the_observer_read():
    rows = [_row('loop_heartbeat', _stamp(0)),
            _row('map_observed', _stamp(1), scene='MAP', floor=1),
            _row('scene_mismatch', _stamp(2), expected='MAP', scene='RESUME_DIALOG'),
            _row('map_observed', _stamp(3), scene='MAP', floor=1)]
    measured = run_metrics.efficiency(rows)
    assert measured['reads'] == 3
    assert measured['steps'] == 1
    assert measured['reads_per_step'] == 3.0


def test_no_heartbeat_means_no_rate():
    measured = run_metrics.efficiency([_row('map_observed', _stamp(1), floor=1)])
    assert measured['reads'] == 1
    assert measured['reads_per_step'] is None


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
        _row('mirror_loop_stopped', _stamp(60), stop_path='no_progress_watchdog',
             reason='the_run_kept_observing_without_writing_anything')])
    measured = run_metrics.portfolio([tmp_path / 'packaged-mirror-1'])
    assert len(measured['runs']) == 1
    assert measured['runs'][0]['seconds'] == 60.0
    assert measured['measures']['mean_seconds']['value'] == 60.0
    assert measured['measures']['reads_per_step']['value'] == 1.0
    assert measured['measures']['no_progress_stop_rate']['value'] == 0.0


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
    assert measure['basis'] == expected, (measure['basis'], expected)
