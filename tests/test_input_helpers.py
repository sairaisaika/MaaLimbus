"""Tests for the input-helper posture a packaged application reports.

The failure this guards is silent: without `maafw/MaaAgentBinary`, MaaFramework's
Maatouch and Minitouch units fail to initialize and every click falls back to
`adb shell input tap`, which the controller reports as succeeded while the game
ignores it. Live 2026-10-12: `dist/MaaLimbus/debug/maafw.log` shows
`AdbShellInput::click [x=125] [y=527]` followed by `Controller.Action.Succeeded`
for a DUNGEON_TEAM slot that never changed, while the source run of the same plan
logged `MaatouchInput` (build/window-debug/debug/maafw.log) and walked six pages.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import input_helpers  # noqa: E402


def app_with_helpers(tmp_path, *, helpers=True, universal=True):
    """A packaged layout: maafw/MaaFramework.dll, optionally with its helpers."""
    root = tmp_path / 'app'
    (root / 'maafw').mkdir(parents=True)
    (root / 'maafw' / 'MaaFramework.dll').write_bytes(b'dll')
    if helpers:
        leaf = root / 'maafw' / 'MaaAgentBinary' / 'maatouch'
        leaf = leaf / 'universal' if universal else leaf / 'x86_64'
        leaf.mkdir(parents=True)
        (leaf / 'maatouch').write_bytes(b'#!')
    return root


def test_a_packaged_app_with_the_helpers_is_quiet(tmp_path):
    root = app_with_helpers(tmp_path)
    state = input_helpers.report(root)
    assert state['packaged'] and state['present'] and state['maatouch']
    assert input_helpers.usable(state)
    assert input_helpers.warning(state) is None
    assert input_helpers.line(state) == 'input helpers: ok (maatouch)'
    assert state['directory'] == str(root / 'maafw' / 'MaaAgentBinary')


def test_a_packaged_app_without_them_names_the_silent_fallback(tmp_path):
    root = app_with_helpers(tmp_path, helpers=False)
    state = input_helpers.report(root)
    assert state['packaged'] and not input_helpers.usable(state)
    warning = input_helpers.warning(state)
    assert 'input helpers missing' in warning
    assert str(root / 'maafw' / 'MaaAgentBinary') in warning
    assert 'adb shell input tap' in warning
    assert 'the game ignores the tap' in warning
    assert input_helpers.line(state) == ('input helpers: MISSING in '
                                        + str(root / 'maafw' / 'MaaAgentBinary'))


def test_an_empty_helper_directory_is_still_missing(tmp_path):
    root = app_with_helpers(tmp_path, helpers=False)
    (root / 'maafw' / 'MaaAgentBinary').mkdir()
    state = input_helpers.report(root)
    assert state['present'] and not input_helpers.usable(state)
    assert input_helpers.warning(state)


def test_a_source_checkout_is_quiet(tmp_path):
    root = tmp_path / 'checkout'
    root.mkdir()
    state = input_helpers.report(root)
    assert not state['packaged']
    assert input_helpers.warning(state) is None
    assert input_helpers.line(state) == 'input helpers: source layout, MaaFw resolves them'
    assert input_helpers.line(state).count('MISSING') == 0


def test_this_repository_is_a_source_checkout():
    assert not input_helpers.report(ROOT)['packaged']


def test_a_local_dist_application_carries_the_helpers():
    """The 2026-10-12 repair, asserted only when the app folder is present."""
    app = ROOT / 'dist' / 'MaaLimbus'
    if not input_helpers.packaged(app):
        pytest.skip('no local dist application in this checkout')
    state = input_helpers.report(app)
    assert input_helpers.usable(state), input_helpers.warning(state)
