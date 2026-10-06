"""ADB controller construction the way MaaToolkit prescribes.

The manual (`docs/zh_cn/2.4-控制方式说明.md:8`) is explicit: an ADB controller's
screencap/input methods come from `MaaToolkitAdbDeviceFind` automatic detection, and
for MuMu 12 discovery supplies the emulator's native `EmulatorExtras` path
(input priority: `EmulatorExtras > Maatouch > MinitouchAndAdbKey > AdbShell`).
Hardcoding methods therefore throws away the emulator-native route: a bare
Encode+Maatouch binding is what this project used before, and MuMu 12 then serves
the touch through the host, which is what grabbed the user's mouse.

Policy: reads may use any discovered binding; input may only be sent when
discovery offers `EmulatorExtras`, unless the caller explicitly opts in to the
fallback. Nothing here decides what to click.
"""
from maa.controller import AdbController
from maa.define import MaaAdbInputMethodEnum
from maa.toolkit import Toolkit

INPUT_EMULATOR_EXTRAS = 8
SCREENCAP_EMULATOR_EXTRAS = 64
INPUT_NAMES = {1: 'AdbShell', 2: 'MinitouchAndAdbKey', 4: 'Maatouch', 8: 'EmulatorExtras'}
SCREENCAP_NAMES = {1: 'EncodeToFileAndPull', 2: 'Encode', 4: 'RawWithGzip', 8: 'RawByNetcat',
                   16: 'MinicapDirect', 32: 'MinicapStream', 64: 'EmulatorExtras'}


def discover(serial, adb_path=None):
    """Find `serial` through MaaToolkit and return its device record."""
    for device in Toolkit.find_adb_devices(adb_path):
        if device.address == serial:
            return {'name': device.name, 'adb_path': str(device.adb_path),
                    'address': device.address,
                    'screencap_methods': int(device.screencap_methods),
                    'input_methods': int(device.input_methods),
                    'config': dict(device.config or {}),
                    'source': 'maa_toolkit_discovery',
                    'screencap_names': names(int(device.screencap_methods), SCREENCAP_NAMES),
                    'input_names': names(int(device.input_methods), INPUT_NAMES)}
    return {'address': serial, 'source': 'not_found', 'screencap_methods': 0,
            'input_methods': 0, 'screencap_names': [], 'input_names': []}


def names(bitmask, table):
    return [name for value, name in sorted(table.items()) if bitmask & value]


def input_policy(record, allow_fallback=True):
    """(allowed, reason) for sending input through this binding.

    The manual's prescription is that discovery decides the methods, so any
    discovered binding may send input. `EmulatorExtras` input is reported when the
    emulator offers it; MuMu 12 here offers it for screencap only, so the reason
    records the methods that will actually be used.
    """
    if record.get('source') != 'maa_toolkit_discovery':
        return False, 'device_not_discovered_by_maa_toolkit'
    offered = int(record.get('input_methods', 0))
    if offered & INPUT_EMULATOR_EXTRAS:
        return True, 'emulator_extras_input'
    if not offered:
        return False, 'no_input_method_offered'
    if allow_fallback:
        return True, 'discovered_input_' + '+'.join(record.get('input_names') or ['unknown'])
    return False, 'emulator_extras_input_unavailable'


def pin_input(record, method_name):
    """Restrict a discovered record to one input method; unknown names are refused."""
    values = {name: value for value, name in INPUT_NAMES.items()}
    if method_name not in values:
        raise ValueError('Unknown ADB input method: ' + method_name)
    value = values[method_name]
    if not int(record.get('input_methods', 0)) & value:
        raise ValueError('Discovered binding does not offer ' + method_name)
    pinned = dict(record)
    pinned['input_methods'] = value
    pinned['input_names'] = [method_name]
    pinned['pinned'] = method_name
    return pinned


def build(record, *, input_enabled):
    """Create the AdbController for a discovered record; Null input when read-only."""
    if record.get('source') != 'maa_toolkit_discovery':
        raise ValueError('Device must be discovered by MaaToolkit before use: ' + str(record))
    methods = int(record['input_methods']) if input_enabled else int(MaaAdbInputMethodEnum.Null)
    return AdbController(record['adb_path'], record['address'],
                         int(record['screencap_methods']), methods, record['config'])
