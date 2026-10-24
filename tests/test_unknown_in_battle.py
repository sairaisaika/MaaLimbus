"""Inside a battle there is no third kind of frame (D129).

Measured 2026-10-24 (`evidence/runtime/packaged-mirror-20261024-142611`): after a
submitted turn a battle turn held 10-14 `window_unknown_wait` rounds at the unknown
interval while the transition path retired after 1-9 polls.  The same animation was
being paid for twice: `looks_like_transition` is a guess written for pages that carry
no control, and a battle's animation carries the battle's own controls, so it fell to
the unknown budget instead of the transition clock.
"""
import json

import pytest

from maalimbus import runner

WAIT_PLAN = {'page': 'UNKNOWN', 'action': 'wait', 'target': None, 'node': None,
             'expect': (), 'reason': 'the_page_could_not_be_named', 'advance': False}

CONTROLS = [{'text': 'Win', 'box': [1600, 803, 60, 22], 'score': 0.95},
            {'text': 'Rate', 'box': [1668, 803, 60, 22], 'score': 0.95},
            {'text': 'MAX', 'box': [1770, 20, 60, 30], 'score': 0.99}]


class _Journal:
    def __init__(self, directory):
        self.path = directory / 'events.jsonl'

    def record(self, event, **fields):
        row = {'event': event}
        row.update(fields)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


class _Observer:
    """A frozen frame that carries the battle's own controls but names no page."""

    def __init__(self):
        self.calls = 0

    def record(self):
        self.calls += 1
        return {'scene': 'UNKNOWN', 'image_sha256': 'same', 'size': [1920, 1080],
                'ocr': list(CONTROLS)}


class _Fixed:
    def __init__(self, ocr):
        self.ocr = ocr

    def record(self):
        rows = [dict({'score': 0.9}, **row) for row in self.ocr]
        return {'scene': 'UNKNOWN', 'image_sha256': 'same', 'size': [1920, 1080],
                'ocr': rows}


def _run(tmp_path, monkeypatch, last_page=None, ocr=None, **settings):
    loop = runner.MirrorRunner(runner.FakeDevice(),
                               settings={'rounds': 1, 'interval': 4, **settings},
                               directory=tmp_path, journal=_Journal(tmp_path))
    if last_page is not None:
        loop.state['last_named_page'] = last_page
    loop.observer = _Observer() if ocr is None else _Fixed(ocr)
    monkeypatch.setattr(runner, 'plan_step', lambda page, **kw: dict(WAIT_PLAN))
    monkeypatch.setattr(runner, 'observe', lambda observer, deadline=None: observer.record())
    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: None)
    loop.run(steps=1, interval=4, round_limit=1)
    return loop


def _events(tmp_path, name):
    path = tmp_path / 'events.jsonl'
    if not path.exists():
        return []
    return [row for row in (json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
                            if line.strip()) if row['event'] == name]


def test_an_unreadable_frame_in_a_battle_is_a_transition(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, last_page='BATTLE_HUD')
    assert _events(tmp_path, 'window_transition_wait'), 'the transition path must take it'
    assert not _events(tmp_path, 'window_unknown_wait'), 'it may not spend the unknown budget'


def test_a_frozen_battle_frame_is_still_a_transition(tmp_path, monkeypatch):
    """The sha does not change while the animation holds, and that is not a page."""
    _run(tmp_path, monkeypatch, last_page='BATTLE_PLANNING')
    assert _events(tmp_path, 'window_transition_wait')


def test_a_control_word_does_not_stop_it_but_does_stop_the_other_rule(tmp_path, monkeypatch):
    """The counter-example: `looks_like_transition` says no, and D129 says go on.

    A battle frame can print `Select` or `Skip` while it is still the turn's animation.
    Outside a battle that word is exactly what makes the frame a page this reader does
    not know yet, which is why the rule is *scoped to a battle* and not loosened.
    """
    record = {'scene': 'UNKNOWN', 'image_sha256': 'same', 'size': [1920, 1080],
              'ocr': [{'text': 'Select', 'box': [900, 579, 114, 34]}]}
    assert runner.looks_like_transition(record) is False
    _run(tmp_path, monkeypatch, last_page='BATTLE_HUD', ocr=record['ocr'])
    assert _events(tmp_path, 'window_transition_wait')


def test_the_frame_is_journalled_once_per_episode(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, last_page='BATTLE_HUD')
    rows = _events(tmp_path, 'battle_frame_unreadable')
    assert len(rows) == 1
    assert rows[0]['after'] == 'BATTLE_HUD'
