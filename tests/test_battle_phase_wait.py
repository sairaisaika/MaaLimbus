"""A battle animation is not an unknown page (D126).

The measured archive shows 9-17 consecutive unreadable reads right after `BATTLE_HUD`,
each costing one read plus one wait, while the game plays the fight and offers nothing to
click.  Polling that phase at the page's own pace spends reads for no information, so the
wait takes its interval from the page that came before it -- and says which wait it was.
"""
import json

from maalimbus import runner

UNKNOWN_PLAN = {'page': 'UNKNOWN', 'action': 'wait', 'target': None, 'node': None,
                'expect': (), 'reason': 'the_page_could_not_be_named', 'advance': False}


class _Journal:
    def __init__(self, directory):
        self.path = directory / 'events.jsonl'

    def record(self, event, **fields):
        row = {'event': event}
        row.update(fields)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


class _Observer:
    def __init__(self, scene='UNKNOWN'):
        self.scene = scene

    def record(self):
        return {'scene': self.scene, 'image_sha256': 'same', 'size': [1920, 1080],
                'ocr': []}


def _waits(tmp_path, monkeypatch, *, before, **settings):
    loop = runner.MirrorRunner(runner.FakeDevice(), settings={'rounds': 1, 'interval': 0,
                                                             **settings},
                               directory=tmp_path, journal=_Journal(tmp_path))
    loop.observer = _Observer()
    sleeps = []
    monkeypatch.setattr(runner, 'plan_step', lambda page, **kw: dict(UNKNOWN_PLAN))
    monkeypatch.setattr(runner, 'observe',
                        lambda observer, deadline=None: {'scene': 'UNKNOWN',
                                                         'image_sha256': 'same',
                                                         'size': [1920, 1080], 'ocr': []})
    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: sleeps.append(seconds))
    loop.state['last_named_page'] = before
    loop.run(steps=1, interval=0, round_limit=1)
    rows = [json.loads(line) for line in (tmp_path / 'events.jsonl').read_text(
        encoding='utf-8').splitlines()]
    waits = [row for row in rows if row['event'] == 'window_unknown_wait']
    return waits, sleeps


def test_a_battle_phase_wait_uses_its_own_interval(tmp_path, monkeypatch):
    waits, sleeps = _waits(tmp_path, monkeypatch, before='BATTLE_HUD',
                           battle_phase_interval=2.5, unknown_interval=1.5)
    assert waits, 'the wait was not journalled'
    assert waits[0]['interval_s'] == 2.5
    assert waits[0]['battle_phase'] is True
    assert waits[0]['after'] == 'BATTLE_HUD'
    assert 2.5 in sleeps, sleeps[:3]


def test_an_unreadable_non_battle_page_keeps_the_page_interval(tmp_path, monkeypatch):
    waits, sleeps = _waits(tmp_path, monkeypatch, before='MAP',
                           battle_phase_interval=2.5, unknown_interval=1.5)
    assert waits[0]['interval_s'] == 1.5
    assert waits[0]['battle_phase'] is False
    assert 1.5 in sleeps and 2.5 not in sleeps, sleeps[:3]


def test_the_battle_phase_interval_is_a_bounded_setting():
    assert 1.0 <= runner.settings().battle_phase_interval <= 10.0
    for bad in (0, -1, 31):
        try:
            runner.settings({'battle_phase_interval': bad})
        except ValueError:
            continue
        raise AssertionError(f'{bad} was accepted')
