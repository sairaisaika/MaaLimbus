"""A readable floor header with no pack line is not a page this reader can name.

Measured 2026-10-25: `evidence/runtime/packaged-mirror-20261025-022715` stood on a map
whose OCR held only `'Exploring Floor5' [60,127,338,49]`; `map_header` returned None, the
page stayed UNKNOWN, and the run spent its whole 420 s budget on 136 events with 0 clicks.
The header is evidence the reader understood the page, so the loop names what it lacks
instead of waiting out the unknown clock.
"""
import json
import pathlib
import types

from maalimbus import runner

HEADER = {'text': 'Exploring Floor 5', 'box': [60, 127, 338, 49], 'score': .96}


def _record(scene='UNKNOWN', ocr=(HEADER,)):
    return {'scene': scene, 'frame': 'frame-0001', 'size': [1920, 1080],
            'image_sha256': 'x' * 64, 'ocr': list(ocr), 'local_ocr': []}


class _Journal:
    """Write the rows the loop emits, so the assertions read the run's own record."""

    def __init__(self, directory):
        self.path = pathlib.Path(directory) / 'events.jsonl'
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event, **fields):
        row = dict(fields, event=event)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, default=str) + chr(10))


def _run(tmp_path, scenes):
    loop = runner.MirrorRunner(runner.FakeDevice(), journal=_Journal(tmp_path),
                              settings={'rounds': 1, 'interval': 0, 'steps': 6,
                                        'stall_seconds': 0, 'progress_seconds': 0},
                              directory=tmp_path)
    seen = {'n': 0}

    def observe(*_a, **_k):
        seen['n'] += 1
        return scenes[min(seen['n'] - 1, len(scenes) - 1)]

    original = runner.observe
    runner.observe = observe
    try:
        result = loop.run(steps=6, interval=0, round_limit=1)
    finally:
        runner.observe = original
    return loop, result, seen['n']


def _events(tmp_path, name):
    path = pathlib.Path(tmp_path) / 'events.jsonl'
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    return [row for row in rows if row.get('event') == name]


def test_a_readable_header_without_a_pack_line_names_the_ending(tmp_path):
    loop, result, reads = _run(tmp_path, [_record()])
    assert result['passed'] is False
    assert loop.state['session_ended'] == runner.MAP_HEADER_UNIDENTIFIED
    notes = _events(tmp_path, 'map_header_without_a_pack_line')
    assert [row['round'] for row in notes] == [1, 2, 3, 4, 5, 6]
    assert notes[0]['floor_text'] == 'Exploring Floor 5'
    assert 'waited_s' in notes[0]
    assert reads <= 8, 'it waits for its clock, it does not idle'


def test_a_page_without_a_header_still_uses_the_unknown_budget(tmp_path):
    loop, _result, _reads = _run(tmp_path, [_record(ocr=())])
    assert _events(tmp_path, 'map_header_without_a_pack_line') == []
    assert loop.state['session_ended'] != runner.MAP_HEADER_UNIDENTIFIED


def test_a_named_map_page_is_not_touched_by_this_rule(tmp_path):
    map_record = _record(scene='MAP', ocr=[HEADER, {'text': 'Sunk Gloom', 'box': [64, 190, 114, 18], 'score': .99}])
    loop, _result, _reads = _run(tmp_path, [map_record])
    assert _events(tmp_path, 'map_header_without_a_pack_line') == []


def test_a_map_with_no_pack_line_still_offers_a_click(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'candidates_of', lambda directory, record: ('MAP', [[100, 200, 40, 40]]))
    loop, result, _reads = _run(tmp_path, [_record()])
    notes = _events(tmp_path, 'acted_on_a_map_without_a_pack_line')
    assert len(notes) == 1 and notes[0]['point'] == [120, 220]
    assert loop.state['map_acted_once'] is True
    assert loop.device.clicks == [[120, 220]]


def test_a_panel_on_screen_is_never_acted_on_as_a_map(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'candidates_of', lambda directory, record: ('MAP', [[100, 200, 40, 40]]))
    panel = {'text': 'Enter', 'box': [1800, 900, 90, 40], 'score': .98}
    loop, _summary, _reads = _run(tmp_path, [_record(ocr=(HEADER, panel))])
    assert _events(tmp_path, 'acted_on_a_map_without_a_pack_line') == []
    assert loop.device.clicks == []


def test_a_run_that_already_clicked_a_map_keeps_its_action_rights(tmp_path):
    """A header-only screen ends a run that never acted on a map, not one mid-floor."""
    loop, _result, _reads = _run(tmp_path, [_record()])
    assert loop.state['session_ended'] == runner.MAP_HEADER_UNIDENTIFIED
