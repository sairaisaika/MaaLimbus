"""A preference edit is not in effect until a run says which file it loaded (D282)."""
import ast
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.runtime_paths import CONFIG_FILES, apply_sync, plan_sync  # noqa: E402


def test_a_missing_source_file_is_reported_not_copied(tmp_path):
    rows = plan_sync(tmp_path / 'a', tmp_path / 'b', ('user-team-profiles.json',))
    assert rows == [{'name': 'user-team-profiles.json', 'action': 'missing',
                     'detail': str(tmp_path / 'a' / 'user-team-profiles.json')}]


def test_an_identical_file_is_same_and_a_different_one_is_copied(tmp_path):
    source, target = tmp_path / 'a', tmp_path / 'b'
    source.mkdir(); target.mkdir()
    (source / 'user-team-profiles.json').write_text('{"teams": []}', encoding='utf-8')
    (target / 'user-team-profiles.json').write_text('{"teams": []}', encoding='utf-8')
    assert [row['action'] for row in plan_sync(source, target, ('user-team-profiles.json',))] == ['same']
    (target / 'user-team-profiles.json').write_text('{"teams": [1]}', encoding='utf-8')
    assert [row['action'] for row in plan_sync(source, target, ('user-team-profiles.json',))] == ['copied']


def test_apply_copies_only_the_reported_files_and_is_idempotent(tmp_path):
    source, target = tmp_path / 'a', tmp_path / 'b'
    source.mkdir(); target.mkdir()
    (source / 'user-team-profiles.json').write_text('{"teams": [2]}', encoding='utf-8')
    (target / 'user-ledger.json').write_text('{"run": 1}', encoding='utf-8')
    first = apply_sync(source, target, ('user-team-profiles.json', 'user-mirror-settings.json'))
    assert [row['action'] for row in first] == ['copied', 'missing']
    assert (target / 'user-team-profiles.json').read_text(encoding='utf-8') == '{"teams": [2]}'
    assert (target / 'user-ledger.json').read_text(encoding='utf-8') == '{"run": 1}'
    second = apply_sync(source, target, ('user-team-profiles.json',))
    assert [row['action'] for row in second] == ['same']


def test_the_start_record_names_the_directory_and_the_file_it_loaded():
    tree = ast.parse((ROOT / 'agent' / 'recognition.py').read_text(encoding='utf-8'))
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == 'record' and node.args
             and isinstance(node.args[0], ast.Constant)
             and node.args[0].value == 'mirror_loop_start']
    assert len(calls) == 1, calls
    keys = {kw.arg for kw in calls[0].keywords}
    assert {'data_directory', 'team_profiles'} <= keys, keys


def test_the_preference_whitelist_never_names_a_ledger():
    assert CONFIG_FILES
    assert all('ledger' not in name and 'transaction' not in name for name in CONFIG_FILES)
