"""A map frame must say which destinations it offered, not only what it showed.

D62 measured the ladder by the page chrome -- header, pack, panel, battle and clear boxes
in ``map_observed`` -- and had to call `rarely` a lower bound: a viewport gesture can bring
a node into view without moving any of those.  The offer lived only in the loop
(`candidates_of`), so the journal could not answer the question that judged the rung.

This writer records the offer the loop was actually allowed to choose from (adjacency
filter included) as ``map_nodes_offered``, and ``run_metrics.rung_effect`` reads it as a
second signal beside the chrome.  The counter-example is the whole point of the first test:
without the row, the archive cannot see a node move, and the audit says so instead of
reporting a change it did not measure.
"""
import json
from pathlib import Path

import pytest

import maalimbus.runner as runner
from maalimbus.runner import FakeDevice, MirrorRunner


class _Journal(object):
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'events.jsonl'

    def record(self, event, **fields):
        line = json.dumps(dict(fields, event=event), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + chr(10))


def _events(directory):
    path = Path(directory) / 'events.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


BOXES = [[100, 200, 40, 40], [300, 400, 40, 40]]


def _run(tmp_path, monkeypatch, boxes=None):
    frame = 'frame-0001.png'
    # `step` names the frame file for its record when no image object is handed over.
    (Path(tmp_path) / 'frame-0001.json').write_text(
        json.dumps({'image_sha256': 'a' * 64, 'frame': 1}), encoding='utf-8')
    monkeypatch.setattr(runner, 'candidates_of',
                        lambda directory, record, **kw: (frame, list(BOXES if boxes is None else boxes)))
    plan = {'page': 'MAP', 'action': 'click', 'target': [120, 220, 40, 40], 'node': None,
            'expect': ('MAP',), 'reason': 'map_node_click_is_the_only_proven_forward_input',
            'advance': False}
    monkeypatch.setattr(runner, 'plan_step', lambda *args, **kwargs: dict(plan))
    monkeypatch.setattr(runner, 'observe',
                        lambda observer, deadline=None: {'scene': 'MAP',
                                                         'image_sha256': 'same',
                                                         'size': [1920, 1080], 'ocr': []})
    monkeypatch.setattr(runner.time, 'sleep', lambda *_a, **_k: None)
    loop = MirrorRunner(FakeDevice(), settings={'rounds': 1, 'interval': 0, 'steps': 1,
                                                'stall_seconds': 0, 'progress_seconds': 0},
                        directory=tmp_path, journal=_Journal(tmp_path))
    loop.run(steps=1, interval=0, round_limit=1)
    return [event for event in _events(tmp_path) if event['event'] == 'map_nodes_offered']


def test_the_offer_is_written_for_a_map_frame(tmp_path, monkeypatch):
    notes = _run(tmp_path, monkeypatch)
    assert notes, [event['event'] for event in _events(tmp_path)]
    # Every MAP step of the run writes its own offer; the row is per observation, not
    # per run, because the offered set is what a later rung measurement must compare.
    assert {note['offered'] for note in notes} == {2}
    assert notes[0]['offered'] == 2
    assert notes[0]['boxes'] == BOXES
    assert notes[0]['reason'] == 'the_destinations_this_map_frame_offered_to_the_loop'


def test_an_empty_offer_is_still_written(tmp_path, monkeypatch):
    notes = _run(tmp_path, monkeypatch, boxes=[])
    assert notes and notes[0]['offered'] == 0 and notes[0]['boxes'] == []


def test_the_row_carries_the_party_it_was_filtered_against(tmp_path, monkeypatch):
    notes = _run(tmp_path, monkeypatch)
    # No party on the synthetic frame: the field must be present and null, not absent.
    assert 'party' in notes[0] and notes[0]['party'] is None


def test_a_non_map_page_offers_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'candidates_of', lambda directory, record, **kw: (None, None))
    monkeypatch.setattr(runner, 'plan_step',
                        lambda *args, **kwargs: {'page': 'DRIVE', 'action': 'none',
                                                 'target': None, 'node': None,
                                                 'expect': (), 'reason': 'a_drive_plan',
                                                 'advance': False})
    monkeypatch.setattr(runner, 'observe',
                        lambda observer, deadline=None: {'scene': 'DRIVE',
                                                         'image_sha256': 'same',
                                                         'size': [1920, 1080], 'ocr': []})
    monkeypatch.setattr(runner.time, 'sleep', lambda *_a, **_k: None)
    loop = MirrorRunner(FakeDevice(), settings={'rounds': 1, 'interval': 0, 'steps': 1,
                                                'stall_seconds': 0, 'progress_seconds': 0},
                        directory=tmp_path, journal=_Journal(tmp_path))
    loop.run(steps=1, interval=0, round_limit=1)
    assert [event for event in _events(tmp_path) if event['event'] == 'map_nodes_offered'] == []
