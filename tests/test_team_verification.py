"""Which saved team is in play, and whether the plan belongs to it (D90).

The rotation picks the saved team the run *enters* with. A resumed exploration
keeps the team it was started with, so the pre-battle page's own ``TEAMS # N``
header is the only place that says which team the game actually deployed. Live
run packaged-mirror-20261024-001120 planned slot 2's Charge/Tremor keywords and
shopped for them while the exploration it resumed was on slot 1.
"""
import json
import types

import pytest

import maalimbus.runner as runner
from maalimbus.vision import Text


class _Journal:
    def __init__(self, directory):
        self.path = directory / 'events.jsonl'
        self.path.write_text('', encoding='utf-8')

    def record(self, event, **details):
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'event': event, **details}, ensure_ascii=False) + '\n')


def _events(tmp_path, name):
    rows = [json.loads(line) for line in (tmp_path / 'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    return [row for row in rows if row['event'] == name]


def _loop(tmp_path, *, wanted=2):
    loop = types.SimpleNamespace(
        state={},
        store=types.SimpleNamespace(team_slot=wanted),
        settings=types.SimpleNamespace(team=None),
        journal=_Journal(tmp_path),
        artifacts={},
        last_event=None,
        _last_page=None,
    )
    # The real journal writer, on a bare object: the fields it takes are what the
    # archive will hold, so the test must not hand-write its own version.
    loop.note = types.MethodType(runner.MirrorRunner.note, loop)
    return loop


def _record(header='TEAMS # 1'):
    ocr = [{'text': header, 'box': [500, 170, 120, 30], 'score': 0.99}]
    for index in range(1, runner.CARD_COUNT + 1):
        ocr.append({'text': f'Sinner {index}', 'box': [100 + index * 90, 400, 80, 30], 'score': 0.9})
    return {'size': [1920, 1080], 'ocr': ocr}


def _controls():
    return {'pre_battle.card_%02d' % index: [100 + index * 90, 380, 80, 70]
            for index in range(1, runner.CARD_COUNT + 1)}


def test_the_pre_battle_page_carries_its_header():
    team = runner.team_state(_record('TEAMS # 1'), _controls())
    assert team is not None
    assert team['saved_team'] == 1


def test_a_page_without_a_header_says_nothing():
    team = runner.team_state(_record('TEAMS'), _controls())
    assert team is not None
    assert team['saved_team'] is None


def test_the_screen_and_the_rotation_agree():
    assert runner.team_verdict(2, 2) == {'kind': 'verified', 'seen': 2, 'wanted': 2}


def test_a_resumed_run_can_have_another_team_in_play():
    assert runner.team_verdict(1, 2) == {'kind': 'mismatch', 'seen': 1, 'wanted': 2}


def test_an_unreadable_header_is_not_a_mismatch():
    assert runner.team_verdict(None, 2)['kind'] is None
    assert runner.team_verdict(1, None)['kind'] is None


def test_the_gift_plan_follows_the_team_the_game_deployed():
    assert runner.gift_slot(1, 2) == 1


def test_the_gift_plan_falls_back_to_the_rotation():
    assert runner.gift_slot(None, 2) == 2
    assert runner.gift_slot(None, None) is None


def test_a_verified_team_is_written_with_both_slots(tmp_path):
    loop = _loop(tmp_path, wanted=2)
    verdict = runner.MirrorRunner._check_team(loop, {'saved_team': 2})
    assert verdict['kind'] == 'verified'
    assert loop.state['team_seen'] == 2
    assert 'team_mismatch' not in loop.state
    rows = _events(tmp_path, 'team_verified')
    assert len(rows) == 1
    assert rows[0]['seen'] == 2 and rows[0]['wanted'] == 2


def test_a_mismatch_is_kept_for_the_gift_plan(tmp_path):
    loop = _loop(tmp_path, wanted=2)
    runner.MirrorRunner._check_team(loop, {'saved_team': 1})
    assert loop.state['team_seen'] == 1
    assert loop.state['team_mismatch'] == {'kind': 'mismatch', 'seen': 1, 'wanted': 2}
    rows = _events(tmp_path, 'team_mismatch')
    assert len(rows) == 1 and rows[0]['seen'] == 1


def test_an_unreadable_team_writes_no_verdict(tmp_path):
    loop = _loop(tmp_path, wanted=2)
    verdict = runner.MirrorRunner._check_team(loop, {'saved_team': None})
    assert verdict['kind'] is None
    assert loop.state == {}
    assert _events(tmp_path, 'team_verified') == []
    assert _events(tmp_path, 'team_mismatch') == []


def test_the_shop_plan_states_where_its_slot_came_from():
    source = (runner.__file__, open(runner.__file__, encoding='utf-8').read())
    text = source[1]
    assert "slot=gift_slot(state.get('team_seen'),self.store.team_slot)" in text
    assert "slot_source='screen' if state.get('team_seen') is not None else 'rotation'" in text
