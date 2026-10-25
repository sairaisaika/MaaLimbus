"""D187: reads per input, grouped by the page the input was sent from."""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

import maalimbus.run_metrics as m


def _stamp(second):
    return '2026-10-25T00:00:%02d.000+00:00' % second


def _run(directory, rows):
    (directory / 'events.jsonl').write_text(
        '\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')


def _stop(second=90):
    return {'event': 'mirror_loop_stopped', 'utc': _stamp(second), 'stop_path': 'agent_loop'}


def test_reads_are_counted_until_the_next_input(tmp_path):
    rows = []
    for index in range(6):
        rows.append({'event': 'window_intent', 'utc': _stamp(index + 1), 'page': 'MAP',
                     'reason': 'r%d' % index})
        for _ in range(2 if index == 0 else 1):
            rows.append({'event': 'map_observed', 'utc': _stamp(index + 1), 'scene': 'MAP'})
    rows.append(_stop())
    _run(tmp_path, rows)
    row = m.reads_by_page([tmp_path])['MAP']
    # six inputs: the first cost two reads, the rest one each -> values [1,1,1,1,1,2]
    assert row['inputs'] == 6
    assert row['median'] == 1
    assert row['p90'] == 2


def test_a_page_with_too_few_inputs_is_not_a_median(tmp_path):
    rows = [
        {'event': 'window_intent', 'utc': _stamp(1), 'page': 'BATTLE_HUD', 'reason': 'a'},
        {'event': 'battle_observed', 'utc': _stamp(2), 'scene': 'BATTLE_HUD'},
        _stop(),
    ]
    _run(tmp_path, rows)
    assert m.reads_by_page([tmp_path]) == {}


def test_a_legacy_run_is_not_quoted_as_today(tmp_path):
    rows = []
    for index in range(6):
        rows.append({'event': 'window_intent', 'utc': _stamp(index + 1), 'page': 'MAP',
                     'reason': 'r%d' % index})
        rows.append({'event': 'map_observed', 'utc': _stamp(index + 1), 'scene': 'MAP'})
    _run(tmp_path, rows)
    assert m.reads_by_page([tmp_path]) == {}


def test_the_floor_and_the_ceiling_are_both_reported(tmp_path):
    rows = []
    for index in range(6):
        rows.append({'event': 'window_intent', 'utc': _stamp(index + 1), 'page': 'MAP',
                     'reason': 'r%d' % index})
        for _ in range(index + 1):
            rows.append({'event': 'map_observed', 'utc': _stamp(index + 1), 'scene': 'MAP'})
    rows.append(_stop())
    _run(tmp_path, rows)
    row = m.reads_by_page([tmp_path])['MAP']
    assert row['inputs'] == 6
    assert row['median'] == 4
    assert row['p90'] >= row['median']


def test_a_guard_probe_is_not_a_read(tmp_path):
    rows = []
    for index in range(6):
        rows.append({'event': 'window_intent', 'utc': _stamp(index + 1), 'page': 'MAP',
                     'reason': 'r%d' % index})
        rows.append({'event': 'map_observed', 'utc': _stamp(index + 1), 'scene': 'MAP'})
        rows.append({'event': 'scene_mismatch', 'utc': _stamp(index + 1)})
    rows.append(_stop())
    _run(tmp_path, rows)
    row = m.reads_by_page([tmp_path])['MAP']
    assert row['median'] == 1
    assert row['probes'] == 1


def test_the_guard_chain_probes_one_frame_not_four():
    """A guard chain (LimbusSafety/LimbusExpired/LimbusDefeat/MirrorEntryConfirm) asks about
    the same picture; the recognition cache is what keeps that to one OCR per frame, so the
    rows must share a frame id rather than each name a new one (D191)."""
    import collections
    import pytest
    try:
        archives = m._archives()
    except Exception:  # pragma: no cover - no corpus on this machine
        pytest.skip('no archive')
    rows = 0
    duplicated = 0
    for directory in archives:
        events = m._rows_of(directory)
        if not m.capability(events, directory)['can_write_a_stop']:
            continue
        frames = collections.Counter(row.get('frame') for row in events
                                     if row.get('event') == 'scene_mismatch')
        rows += sum(frames.values())
        duplicated += sum(count - 1 for count in frames.values())
    if not rows:
        pytest.skip('no guard probe in the corpus')
    assert duplicated / rows > 0.5, 'the guard probes stopped sharing a frame'
