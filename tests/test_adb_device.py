"""ADB binding policy: discovery decides the methods, never a hand-picked pair.

Offline contracts only; no test here contacts an emulator.
"""
import pytest

from maalimbus.adb_device import (INPUT_EMULATOR_EXTRAS, build, discover, input_policy,
                                  names, pin_input, INPUT_NAMES, SCREENCAP_NAMES)

DISCOVERED_MUMU = {
    'name': 'MuMu安卓设备-1-MuMuPlayer v5+', 'address': '127.0.0.1:16416',
    'adb_path': 'D:/Program Files/Netease/MuMu/nx_main/adb.exe',
    'screencap_methods': 64, 'input_methods': 1 | 2 | 4,
    'config': {'extras': {'mumu': {'enable': True}}}, 'source': 'maa_toolkit_discovery',
    'screencap_names': ['EmulatorExtras'], 'input_names': ['AdbShell', 'MinitouchAndAdbKey', 'Maatouch'],
}
DISCOVERED_WITH_EXTRAS = dict(DISCOVERED_MUMU, input_methods=1 | 2 | 4 | 8,
                             input_names=['AdbShell', 'MinitouchAndAdbKey', 'Maatouch', 'EmulatorExtras'])
NOT_DISCOVERED = {'address': '127.0.0.1:16416', 'source': 'not_found',
                  'input_methods': 0, 'screencap_methods': 0}


def test_discovery_supplies_the_binding_and_reports_method_names():
    allowed, reason = input_policy(DISCOVERED_MUMU)
    assert allowed and reason == 'discovered_input_AdbShell+MinitouchAndAdbKey+Maatouch'
    assert DISCOVERED_MUMU['screencap_methods'] == 64        # EmulatorExtras screencap
    assert names(64, SCREENCAP_NAMES) == ['EmulatorExtras']
    assert names(1 | 2 | 4 | 8, INPUT_NAMES) == \
        ['AdbShell', 'MinitouchAndAdbKey', 'Maatouch', 'EmulatorExtras']


def test_emulator_extras_input_is_reported_when_the_emulator_offers_it():
    allowed, reason = input_policy(DISCOVERED_WITH_EXTRAS)
    assert allowed and reason == 'emulator_extras_input'
    assert DISCOVERED_WITH_EXTRAS['input_methods'] & INPUT_EMULATOR_EXTRAS


def test_undiscovered_or_method_less_bindings_may_not_send_input():
    assert input_policy(NOT_DISCOVERED) == (False, 'device_not_discovered_by_maa_toolkit')
    empty = dict(DISCOVERED_MUMU, input_methods=0, input_names=[])
    assert input_policy(empty) == (False, 'no_input_method_offered')
    assert input_policy(DISCOVERED_MUMU, allow_fallback=False) == \
        (False, 'emulator_extras_input_unavailable')
    with pytest.raises(ValueError):
        build(NOT_DISCOVERED, input_enabled=False)


def test_pinning_limits_input_to_one_discovered_method_only():
    pinned = pin_input(DISCOVERED_MUMU, 'AdbShell')
    assert pinned['input_methods'] == 1 and pinned['input_names'] == ['AdbShell']
    assert pinned['pinned'] == 'AdbShell'
    assert DISCOVERED_MUMU['input_methods'] == 1 | 2 | 4      # original untouched
    with pytest.raises(ValueError):
        pin_input(DISCOVERED_MUMU, 'EmulatorExtras')          # not offered here
    with pytest.raises(ValueError):
        pin_input(DISCOVERED_MUMU, 'Minitouch')


def test_discovery_record_shape_comes_from_maatoolkit():
    """`discover` must be the only constructor input; a stub proves the contract."""
    import inspect
    source = inspect.getsource(discover)
    assert 'Toolkit.find_adb_devices' in source
    assert 'maa_toolkit_discovery' in source
