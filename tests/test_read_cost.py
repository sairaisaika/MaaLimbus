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
