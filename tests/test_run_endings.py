"""Every run ends in exactly one of four ways, and every ending names its writer.

The census in `tools/audit_runs.py` printed `stopped: 81  died_without_a_stop: 51` over
142 retained runs on 2026-10-23.  The two numbers do not add up because ten runs ended on
`mirror_loop_error` alone: neither a stop nor a death, so neither column was counted while
the denominator still included them.  These tests hold the four buckets apart, and hold
the writers to a closed vocabulary of paths.
"""
import ast
import importlib.util
import pathlib

import pytest

from maalimbus import pages, run_metrics

REPO = pathlib.Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location('audit_runs',
                                                  REPO / 'tools' / 'audit_runs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stop(**fields):
    row = {'event': 'mirror_loop_stopped', 'reason': 'loop_deadline_exceeded'}
    row.update(fields)
    return row


def test_a_run_that_stopped_names_the_writer():
    assert run_metrics.ending([{'event': 'loop_heartbeat'}, _stop(stop_path='agent_loop')]) == {
        'kind': 'stop', 'path': 'agent_loop', 'reason': 'loop_deadline_exceeded'}


def test_a_run_that_ended_on_an_error_is_its_own_bucket():
    end = run_metrics.ending([{'event': 'mirror_loop_error', 'error': 'boom',
                               'error_type': 'RuntimeError', 'stop_path': 'agent_loop'}])
    assert end == {'kind': 'error', 'path': 'agent_loop', 'reason': 'RuntimeError'}


def test_an_error_that_recorded_no_reason_still_says_so():
    end = run_metrics.ending([{'event': 'mirror_loop_error'}])
    assert end['kind'] == 'error'
    assert end['reason'] == 'an_error_was_recorded_without_a_reason'


def test_a_run_with_no_ending_record_died():
    assert run_metrics.ending([{'event': 'map_observed', 'floor': 2}]) == {
        'kind': 'died', 'path': 'process_died', 'reason': None}


def test_a_run_with_no_events_is_not_a_death():
    assert run_metrics.ending([]) == {'kind': 'no_events', 'path': None, 'reason': None}


def test_a_stop_written_before_the_path_existed_says_unrecorded():
    assert run_metrics.ending([_stop()])['path'] == 'unrecorded'


def test_the_four_buckets_partition_any_corpus():
    corpora = [
        [],
        [_stop(stop_path='stall_watchdog')],
        [{'event': 'mirror_loop_error'}],
        [{'event': 'map_observed'}],
    ]
    kinds = [run_metrics.ending(corpus)['kind'] for corpus in corpora]
    assert set(kinds) == set(run_metrics.ENDING_KINDS)
    assert len(set(kinds)) == len(corpora), 'two corpora shared a bucket'


def test_summarise_carries_the_ending():
    report = run_metrics.summarise([_stop(stop_path='no_progress_watchdog')])
    assert report['ending'] == {'kind': 'stop', 'path': 'no_progress_watchdog',
                                'reason': 'loop_deadline_exceeded'}


def test_an_invented_path_is_reported():
    rows = [_stop(stop_path='the_vibes_ended_it')]
    assert run_metrics.unknown_stop_paths(rows) == ['the_vibes_ended_it']
    assert run_metrics.unknown_stop_paths([_stop(stop_path='agent_loop')]) == []
    assert run_metrics.unknown_stop_paths([_stop()]) == []


def test_the_vocabulary_is_closed_and_the_census_only_paths_are_not_writers():
    assert set(pages.STOP_PATH_WRITERS) <= set(pages.STOP_PATHS)
    assert 'process_died' not in pages.STOP_PATH_WRITERS
    assert 'unrecorded' not in pages.STOP_PATH_WRITERS
    assert all(isinstance(text, str) and text for text in pages.STOP_PATHS.values())


def _ending_calls(source):
    """Every direct write of an ending event, with its keyword names."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        names = [getattr(arg, 'attr', None) or getattr(arg, 'id', None)
                 for arg in [node.func]]
        if not ({'note', 'record', 'journal'} & set(n for n in names if n)):
            continue
        first = node.args[0] if node.args else None
        if not (isinstance(first, ast.Constant) and first.value in run_metrics.STOP_EVENTS):
            continue
        keywords = {kw.arg for kw in node.keywords if kw.arg}
        unpacks = any(kw.arg is None for kw in node.keywords)
        found.append((first.value, node.lineno, keywords, unpacks))
    return found


def test_every_direct_ending_writer_names_a_path():
    """A writer that omits `stop_path` puts the run back in the unrecorded bucket."""
    offenders = []
    for path in (REPO / 'src' / 'maalimbus' / 'runner.py',
                 REPO / 'agent' / 'recognition.py'):
        for event, line, keywords, unpacks in _ending_calls(path.read_text(encoding='utf-8')):
            if 'stop_path' not in keywords and not unpacks:
                offenders.append('%s:%d writes %s with no stop_path'
                                 % (path.name, line, event))
    assert offenders == []


def test_the_gate_would_catch_a_writer_that_forgot():
    source = "def f(self, j):\n j.record('mirror_loop_stopped', reason='x')\n"
    assert [c[0] for c in _ending_calls(source)] == ['mirror_loop_stopped']
    assert 'stop_path' not in _ending_calls(source)[0][2]


def test_the_census_on_the_retained_archive_partitions_it():
    """The numbers that did not add up must now; skipped when the archive is absent."""
    runs = sorted(p.parent for p in
                  (REPO / 'evidence' / 'runtime').glob('packaged-mirror-*/events.jsonl'))
    if not runs:
        pytest.skip('no retained runs in this checkout')
    counts, paths, failed, floors = _tool().census(runs)
    assert sum(counts.values()) == len(runs)
    assert set(counts) <= set(run_metrics.ENDING_KINDS)
    assert sum(paths.values()) == len(runs)
    for name, events, fl, end in failed:
        assert end['kind'] in ('died', 'error')
        assert name and isinstance(events, int)


def test_the_two_census_tools_count_the_same_archive_the_same_way():
    """`audit_silent` used its own rule ("no stop event") and said 61 where this said 51."""
    silent = importlib.util.spec_from_file_location(
        'audit_silent', REPO / 'tools' / 'audit_silent.py')
    module = importlib.util.module_from_spec(silent)
    silent.loader.exec_module(module)
    runs = sorted(p.parent for p in
                  (REPO / 'evidence' / 'runtime').glob('packaged-mirror-*/events.jsonl'))
    if not runs:
        pytest.skip('no retained runs in this checkout')
    counts, _paths, _failed, _floors = _tool().census(runs)
    silent_report = module.summarise(str(REPO / 'evidence' / 'runtime'))['runs']
    assert silent_report['silent'] == counts['died']
    assert silent_report.get('stop', 0) == counts['stop']
    assert silent_report.get('error', 0) == counts['error']
    assert sum(silent_report.values()) == len(runs)
