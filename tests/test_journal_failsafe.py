"""A journal write is a diagnostic, so it may not end a healthy run (D194)."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'agent'), str(ROOT / 'src')]

from recognition import Journal


def _rows(directory):
    return [json.loads(line) for line in
            (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]


def test_a_cycle_is_dropped_by_name_and_the_row_survives(tmp_path):
    loop = {}
    loop['self'] = loop
    Journal(tmp_path).record('map_observed', scene='MAP', cycle=loop, fine=1)
    row = _rows(tmp_path)[0]
    assert row['journal_fields_dropped'] == ['cycle']
    assert row['scene'] == 'MAP' and row['fine'] == 1


def test_a_plain_row_is_written_whole(tmp_path):
    Journal(tmp_path).record('map_observed', scene='MAP', floor=2)
    row = _rows(tmp_path)[0]
    assert 'journal_fields_dropped' not in row
    assert row['scene'] == 'MAP' and row['floor'] == 2


def test_every_dropped_field_is_named(tmp_path):
    loop = {}
    loop['self'] = loop
    Journal(tmp_path).record('x', a=loop, b=set([1]), keep='yes')
    row = _rows(tmp_path)[0]
    assert sorted(row['journal_fields_dropped']) == ['a', 'b']
    assert row['keep'] == 'yes'
