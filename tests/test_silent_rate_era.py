"""A rate must divide by the runs that could have answered (D181).

Before D37 a killed process and a journal that simply stops look identical, so counting
those runs as evidence that the loop dies silently measures the age of the writer, not the
loop.  The 257-run archive splits cleanly: every run that can name a stop path or leave a
harness record either stopped or is counted, and the 65 silent ones all predate both.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

import maalimbus.run_metrics as run_metrics


def _run(*, stop=None, capability=None, ending_kind='died'):
    return {'capability': capability or {'can_write_a_stop': False},
            'ending': {'kind': ending_kind, 'path': stop or 'process_died'}}


def test_a_legacy_run_cannot_inflate_the_rate():
    runs = [_run(capability={'can_write_a_stop': True}, ending_kind='stop'),
            _run(capability={'can_write_a_stop': True}, ending_kind='died'),
            _run(capability={'can_write_a_stop': False}, ending_kind='died')]
    result = run_metrics.silent_rate(runs)
    assert result['value'] == 0.5
    assert result['basis'] == '1 of 2 runs that could write a stop wrote none'


def test_no_capable_run_is_not_a_rate_of_zero():
    result = run_metrics.silent_rate([_run(), _run()])
    assert result['value'] is None
    assert 'no run of 2 could write a stop' in result['basis']
    assert 'no pen' in result['note']


def test_capability_reads_the_rows_not_the_build():
    rows = [{'event': 'mirror_loop_stopped', 'stop_path': 'agent_loop'},
            {'event': 'map_observed', 'seconds': 1.2}]
    got = run_metrics.capability(rows)
    assert got['stop_path'] is True and got['timed'] is True
    assert got['can_write_a_stop'] is True


def test_capability_without_markers_is_false():
    got = run_metrics.capability([{'event': 'window_no_progress'}])
    assert got == {'stop_path': False, 'timed': False, 'harness': False,
                   'can_write_a_stop': False}


def test_a_harness_record_is_a_writer_too(tmp_path):
    (tmp_path / 'harness.json').write_text('{"killed_by_budget": true}', encoding='utf-8')
    got = run_metrics.capability([{'event': 'window_intent'}], tmp_path)
    assert got['harness'] is True and got['can_write_a_stop'] is True
