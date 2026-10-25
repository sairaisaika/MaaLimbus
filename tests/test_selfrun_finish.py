"""The bookkeeping of a self-run: the stop row, the summary, the count (D195)."""
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Journal:
    def __init__(self):
        self.rows = []

    def record(self, event, **fields):
        self.rows.append({'event': event, **fields})

    def frame(self, *args, **kwargs):
        return 'frame-0001'


def _rows(directory):
    return [json.loads(line) for line in (directory / 'events.jsonl').read_text(
        encoding='utf-8').splitlines() if line.strip()] if (directory / 'events.jsonl').exists() else []


def test_the_summary_is_written_after_every_row(tmp_path):
    finish = _module('selfrun_finish')
    journal = finish.Snapshotting(_Journal(), tmp_path, {'passed': False}, every=1)
    journal.record('map_observed', scene='MAP')
    first = json.loads((tmp_path / 'result.json').read_text(encoding='utf-8'))
    journal.record('loop_heartbeat', step=1)
    assert first['passed'] is False
    assert json.loads((tmp_path / 'result.json').read_text(encoding='utf-8')) is not None


def test_a_coarser_snapshot_still_writes_on_demand(tmp_path):
    finish = _module('selfrun_finish')
    journal = finish.Snapshotting(_Journal(), tmp_path, {'passed': True}, every=5)
    journal.record('a')
    assert not (tmp_path / 'result.json').exists()
    journal.snapshot()
    assert json.loads((tmp_path / 'result.json').read_text(encoding='utf-8'))['passed'] is True


def test_the_stop_row_names_the_agent_path(tmp_path):
    finish = _module('selfrun_finish')
    journal = _Journal()
    result = finish.summary(journal, {'passed': True, 'reason': 'the_run_reached_its_goal',
                                      'steps': 12, 'clicks_sent': 7}, {}, tmp_path)
    row = journal.rows[-1]
    assert row['event'] == 'mirror_loop_stopped'
    assert row['reason'] == 'the_run_reached_its_goal' and row['stop_path'] == 'agent_loop'
    assert row['steps'] == 12 and row['clicks_sent'] == 7 and row['passed'] is True
    assert json.loads((tmp_path / 'result.json').read_text(encoding='utf-8'))['passed'] is True
    assert result['passed'] is True


def test_the_summary_survives_a_missing_summary(tmp_path):
    finish = _module('selfrun_finish')
    journal = _Journal()
    finish.summary(journal, None, {}, tmp_path)
    assert journal.rows[-1]['passed'] is False and journal.rows[-1]['reason'] is None


def test_the_tally_counts_events_stop_and_floors():
    finish = _module('selfrun_finish')
    result = finish.tally([{'event': 'map_observed', 'floor': '5'},
                           {'event': 'map_observed', 'floor': '4'},
                           {'event': 'mirror_loop_error', 'reason': 'boom'}], {})
    assert result['events'] == 3 and result['floors'] == [4, 5]
    assert result['stop'] == 'boom' and result['ending'] == 'mirror_loop_error'
