"""A read that does not say how long it took cannot be split into node and wrapper.

D66 attributed 2.45 s per `map_observed` from the gaps between journal lines. A gap starts
when the read's own line was written and lasts until the *next* line, which contains the
next read -- so it can say the reads own the time, and it cannot say whether the node's
screencap+OCR or the loop around it spent it. D68 made every observation writer record its
own `seconds`; this module holds the reader for that field and the gate that keeps the
writers honest.
"""
import ast
import pathlib

import pytest

from maalimbus import run_metrics

REPO = pathlib.Path(__file__).resolve().parents[1]
RECOGNITION = REPO / 'agent' / 'recognition.py'


def _read(seconds=None, event='map_observed', **extra):
    row = {'event': event, **extra}
    if seconds is not None:
        row['seconds'] = seconds
    return row


def test_a_read_that_says_how_long_it_took_is_counted():
    cost = run_metrics.read_cost([_read(2.5), _read(3.5), _read(1.0, 'battle_observed')])
    assert cost['measured'] == 3
    assert cost['seconds'] == 7.0
    assert cost['mean'] == 2.33
    assert cost['by_event']['map_observed']['seconds'] == 6.0
    assert cost['by_event']['map_observed']['mean'] == 3.0


def test_a_read_without_a_number_is_not_zero_seconds():
    cost = run_metrics.read_cost([_read(), _read(), _read(1.0)])
    assert cost['rows'] == 3
    assert cost['measured'] == 1


def test_a_corpus_that_never_timed_a_read_says_not_measured():
    report = run_metrics.read_portfolio([run_metrics.read_cost([_read(), _read()])])
    assert report['value'] is None
    assert report['basis'] == '0 of 2 read(s) carry their own duration'
    assert 'D66' in report['note'] and 'D68' in report['note']


def test_a_row_that_is_not_a_read_is_not_counted():
    cost = run_metrics.read_cost([_read(), {'event': 'window_intent', 'seconds': 9.0},
                                  {'event': 'scene_mismatch', 'seconds': 0.2}])
    assert cost['rows'] == 1
    assert cost['measured'] == 0


def test_a_boolean_is_not_a_duration():
    cost = run_metrics.read_cost([_read(True), _read(2.0)])
    assert cost['measured'] == 1
    assert cost['seconds'] == 2.0


def test_the_median_handles_an_even_count():
    cost = run_metrics.read_cost([_read(1.0), _read(2.0), _read(3.0), _read(4.0)])
    assert cost['median'] == 2.5


def test_the_split_subtracts_the_node_from_the_reads_group():
    cost = run_metrics.read_cost([_read(3.5), _read(3.5)])
    report = run_metrics.read_split([dict(cost, reads_group=11.0)])
    assert report['value']['node_seconds'] == 7.0
    assert report['value']['overhead_seconds'] == 4.0
    assert report['value']['node_mean'] == 3.5


def test_a_run_without_read_durations_is_not_in_the_split():
    cost = run_metrics.read_cost([_read()])
    report = run_metrics.read_split([dict(cost, reads_group=99.0)])
    assert report['value'] is None
    assert 'without read durations' in report['note'] or 'predates D68' in report['note']


def test_a_run_without_gaps_is_not_in_the_split():
    cost = dict(run_metrics.read_cost([_read(1.0)]), reads_group=None)
    assert run_metrics.read_split([cost])['value'] is None


def test_the_portfolio_carries_both_halves_of_the_read_cost():
    portfolio = run_metrics.portfolio([])
    assert set(portfolio) == {'runs', 'measures', 'time', 'reads', 'split'}
    assert portfolio['reads']['value'] is None
    assert portfolio['split']['value'] is None


def _observation_records(source):
    """Every `journal.record('<read event>', ...)` call, with its keyword names."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != 'record' or not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and
                first.value in run_metrics.TIMED_READ_EVENTS):
            continue
        found.append((first.value, node.lineno,
                      {keyword.arg for keyword in node.keywords}))
    return found


def test_every_observation_writer_times_itself():
    records = _observation_records(RECOGNITION.read_text(encoding='utf-8'))
    assert {event for event, _, _ in records} == set(run_metrics.TIMED_READ_EVENTS)
    missing = [(event, line) for event, line, names in records if 'seconds' not in names]
    assert missing == []


def test_the_gate_would_catch_a_writer_that_forgot():
    drifted = ("def run(self):\n"
               "    self.journal.record('map_observed', frame=1, scene='MAP')\n")
    assert _observation_records(drifted)[0][2] == {'frame', 'scene'}


def test_a_comment_is_not_a_duration():
    drifted = ("def run(self):\n"
               "    # seconds=... would go here\n"
               "    self.journal.record('battle_observed', frame=1)\n")
    assert 'seconds' not in _observation_records(drifted)[0][2]


def test_the_tool_says_so_when_there_is_nothing_to_read(tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'audit_time', REPO / 'tools' / 'audit_time.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(['--root', str(tmp_path)]) == 2
    assert 'no run wrote a journal' in capsys.readouterr().out


# -- D70: the read's own seconds, split into the phases that spent them ------------------

def _split(ocr=None, roi=None, classify=None, **extra):
    row = _read(1.0, **extra)
    for key, value in (('ocr_seconds', ocr), ('roi_seconds', roi),
                       ('classify_seconds', classify)):
        if value is not None:
            row[key] = value
    return row


def test_the_three_phases_of_a_read_are_averaged_over_the_reads_that_carry_them():
    phases = run_metrics.read_cost([_split(0.6, 0.2, 0.2), _split(0.4, 0.0, 0.6)])['phases']
    assert phases['measured'] == 2
    assert phases['mean'] == {'ocr_seconds': 0.5, 'roi_seconds': 0.1,
                              'classify_seconds': 0.4}


def test_a_read_that_only_says_its_total_is_not_a_split_of_zero():
    cost = run_metrics.read_cost([_split()])['phases']
    assert cost['measured'] == 0
    assert cost['mean'] == {'ocr_seconds': None, 'roi_seconds': None,
                            'classify_seconds': None}


def test_a_partial_split_is_not_a_split():
    """Two of three phases is a row written by a buggy writer, not a cheap phase."""
    phases = run_metrics.read_cost([_split(0.6, 0.2)])['phases']
    assert phases['measured'] == 0


def test_a_boolean_is_not_a_phase_duration():
    phases = run_metrics.read_cost([_split(True, 0.2, 0.6)])['phases']
    assert phases['measured'] == 0


def test_the_phases_are_only_read_off_the_timed_read_events():
    phases = run_metrics.read_cost([_split(0.6, 0.2, 0.2, event='scene_mismatch')])['phases']
    assert phases['measured'] == 0


def test_a_cached_read_claims_no_phase_time():
    import sys
    sys.path.insert(0, str(REPO / 'agent'))
    source = RECOGNITION.read_text(encoding='utf-8')
    tree = ast.parse(source)
    timing = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == 'timing_fields')
    body = ast.get_source_segment(source, timing)
    assert "record.get('cached')" in body, body
    # A cached read must return nothing rather than three zeros: nothing was spent on it.
    assert 'return {}' in body


def test_every_observation_writer_hands_over_its_phases():
    """The three writers that record a read must pass timing_fields(), not just seconds."""
    source = RECOGNITION.read_text(encoding='utf-8')
    tree = ast.parse(source)
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != 'record' or not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        if first.value not in run_metrics.TIMED_READ_EVENTS:
            continue
        found.setdefault(first.value, []).append(node)
    assert found, 'no observation writer found'
    for event, calls in found.items():
        for call in calls:
            unpacked = [value for keyword in call.keywords
                        if keyword.arg is None for value in [keyword.value]]
            assert unpacked, f'{event} writer at line {call.lineno} records no timing_fields()'
            rendered = [ast.get_source_segment(source, value) or '' for value in unpacked]
            assert any('timing_fields' in text for text in rendered), (
                f'{event} writer at line {call.lineno} records {rendered} instead of timing_fields()')
