"""Every run ends in exactly one of five ways, and every ending names its writer.

The census in `tools/audit_runs.py` printed `stopped: 81  died_without_a_stop: 51` over
142 retained runs on 2026-10-23.  The two numbers do not add up because ten runs ended on
`mirror_loop_error` alone: neither a stop nor a death, so neither column was counted while
the denominator still included them.  These tests hold the five buckets apart, and hold
the writers to a closed vocabulary of paths.

The fifth bucket is D78: `tools/selfrun_mirror.py` enforces the caller's budget from
outside, and on 2026-10-24 00:19 it killed a healthy run that was walking floor 2 into
floor 3 fifteen seconds after the 420 s budget -- shorter than one step, so the loop never
reached its own between-step check and never wrote `mirror_loop_stopped`.  A killed
process cannot write its ending, so the killer now writes `harness.json` into the run's
directory; without that file the same rows still mean a death.
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


def test_the_five_buckets_partition_any_corpus(tmp_path):
    killed = _harness(tmp_path / 'killed')
    corpora = [
        ([], None),
        ([_stop(stop_path='stall_watchdog')], None),
        ([{'event': 'mirror_loop_error'}], None),
        ([{'event': 'map_observed'}], None),
        ([{'event': 'map_observed'}], killed),
    ]
    kinds = [run_metrics.ending(rows, where)['kind'] for rows, where in corpora]
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


def _harness(directory, **fields):
    import json
    directory.mkdir(parents=True, exist_ok=True)
    record = {'killed_by_budget': True, 'stop': 'the_budget_ended_the_run',
              'seconds': 420, 'margin_seconds': 45, 'elapsed_s': 435.2, 'exit': 124}
    record.update(fields)
    (directory / 'harness.json').write_text(json.dumps(record), encoding='utf-8')
    return directory


def test_a_run_the_harness_killed_at_its_budget_is_not_a_death(tmp_path):
    """The killed process cannot write a stop, so the killer's file is the record."""
    _harness(tmp_path)
    end = run_metrics.ending([{'event': 'map_observed'}], tmp_path)
    assert end == {'kind': 'budget', 'path': 'harness_budget',
                   'reason': 'the_budget_ended_the_run'}
    assert 'budget' in run_metrics.ENDING_KINDS


def test_the_same_rows_without_the_harness_file_are_a_death(tmp_path):
    end = run_metrics.ending([{'event': 'map_observed'}], tmp_path)
    assert end == {'kind': 'died', 'path': 'process_died', 'reason': None}


def test_a_harness_file_that_does_not_say_killed_changes_nothing(tmp_path):
    _harness(tmp_path, killed_by_budget=False)
    assert run_metrics.ending([{'event': 'map_observed'}], tmp_path)['kind'] == 'died'


def test_a_budget_end_is_not_reported_as_a_failure(tmp_path):
    """`audit_runs` prints the failed runs; a killed-at-budget run is not one of them."""
    run_dir = tmp_path / 'packaged-mirror-test'
    run_dir.mkdir()
    (run_dir / 'events.jsonl').write_text('{"event": "map_observed"}\n', encoding='utf-8')
    _harness(run_dir)
    counts, _paths, failed, _floors = _tool().census([run_dir])
    assert counts['budget'] == 1 and failed == []


def test_summarise_reads_the_harness_file_only_when_it_is_told_where(tmp_path):
    _harness(tmp_path)
    rows = [{'event': 'loop_heartbeat'}]
    assert run_metrics.summarise(rows)['ending']['kind'] == 'died'
    assert run_metrics.summarise(rows, tmp_path)['ending']['kind'] == 'budget'


def test_the_margin_is_wider_than_the_measured_overshoot():
    """A margin shorter than one step cannot let a healthy loop end itself."""
    spec = importlib.util.spec_from_file_location('selfrun_mirror',
                                                  REPO / 'tools' / 'selfrun_mirror.py')
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # pragma: no cover - the module only runs under __main__
        pass
    measured = (12.3, 12.3, 13.3, 15.2)
    assert module.MARGIN_SECONDS > max(measured)
    source = (REPO / 'tools' / 'selfrun_mirror.py').read_text(encoding='utf-8')
    assert 'timeout=seconds + MARGIN_SECONDS' in source
