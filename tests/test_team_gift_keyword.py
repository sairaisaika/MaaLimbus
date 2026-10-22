"""The gift target must follow the saved team, not the constant `bleed` (D32).

`mirror_initial_keyword` is `saved`, which writes no override, so before this the run
fell back to `runner.Settings`'s hard-coded `bleed` whatever team the profile named.
The charge/burn team then bought bleed gifts.
"""
import json
import shutil

import pytest

from maalimbus.storage import SINNERS
from maalimbus.team_gift_keyword import (active_slot, configured_slot, from_active_team,
                                         systems)

PROFILES = {
    'version': 1,
    'teams': [
        {'slot': 1, 'name': 'bleed', 'keywords': ['Bleed', 'Poise'],
         'formation_keywords': ['Bleed'], 'deployment': list(SINNERS)},
        {'slot': 2, 'name': 'charge', 'keywords': ['Charge', 'Tremor'],
         'formation_keywords': ['Charge', 'Tremor'],
         'deployment': list(reversed(SINNERS))},
    ],
}
LEDGER = {'version': 1, 'active': {'id': 'run', 'team': 2, 'floors': [1]}}


def written(tmp_path, ledger=None):
    directory = tmp_path / 'config'
    directory.mkdir()
    (directory / 'user-team-profiles.json').write_text(
        json.dumps(PROFILES, ensure_ascii=False), encoding='utf-8')
    (directory / 'user-run-ledger.json').write_text(
        json.dumps(ledger if ledger is not None else LEDGER, ensure_ascii=False), encoding='utf-8')
    return directory


def test_the_active_team_names_its_own_system(tmp_path):
    directory = written(tmp_path)
    assert active_slot(directory) == 2
    assert from_active_team(directory) == 'charge', (
        'the charge team must not be given bleed gifts')


def test_the_bleed_team_still_resolves_to_bleed(tmp_path):
    directory = written(tmp_path, {'version': 1, 'active': {'team': 1}})
    assert from_active_team(directory) == 'bleed'


def test_no_active_run_names_nothing(tmp_path):
    directory = written(tmp_path, {'version': 1, 'active': None})
    assert active_slot(directory) is None
    assert from_active_team(directory) is None


def test_missing_profile_or_ledger_is_not_an_error(tmp_path):
    empty = tmp_path / 'empty'
    empty.mkdir()
    assert from_active_team(empty) is None
    directory = written(tmp_path)
    (directory / 'user-run-ledger.json').unlink()
    assert from_active_team(directory) is None


def test_the_same_team_always_names_the_same_system(tmp_path):
    """The profile holds frozensets, so the choice must not follow iteration order."""
    directory = written(tmp_path)
    assert {from_active_team(directory) for _ in range(5)} == {'charge'}


SETTINGS = {'instances': {'tasks': {'optionValues': {
    'mirror_team_mode': {'type': 'select', 'caseName': 'single'},
    'mirror_single_team': {'type': 'select', 'caseName': '2'},
}}}}
ROTATION = {'instances': {'tasks': {'optionValues': {
    'mirror_team_mode': {'type': 'select', 'caseName': 'rotation'},
    'mirror_single_team': {'type': 'select', 'caseName': '2'},
}}}}


def with_settings(tmp_path, settings, ledger=None):
    directory = written(tmp_path, ledger)
    (directory / 'mxu-MaaLimbus.json').write_text(json.dumps(settings), encoding='utf-8')
    return directory


def test_the_task_setting_names_the_team_the_game_will_switch_to(tmp_path):
    """The GUI setting is authoritative: the game switches to it when the task starts."""
    directory = with_settings(tmp_path, SETTINGS, {'version': 1, 'active': {'team': 1}})
    assert configured_slot(directory) == 2
    assert active_slot(directory) == 2, 'the ledger must not override the task setting'
    assert from_active_team(directory) == 'charge'


def test_a_rotation_mode_leaves_the_choice_to_the_rotation(tmp_path):
    directory = with_settings(tmp_path, ROTATION, {'version': 1, 'active': {'team': 1}})
    assert configured_slot(directory) is None
    assert active_slot(directory) == 1, 'rotations still follow the ledger'


def test_the_team_names_every_system_it_is_built_around(tmp_path):
    """charge+tremor is one team; picking one of the two would be the old mistake."""
    directory = with_settings(tmp_path, SETTINGS)
    assert systems(directory) == ('charge', 'tremor')
