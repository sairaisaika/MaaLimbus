"""D168: the run is told which device to drive, and it checks before it drives.

On 2026-10-25 two devices were attached (`2G0YC5ZGCD03H6` and `emulator-5556`), the
framework picked the physical phone by itself, and the attempt wrote zero events and read
like a crash.  An address that is asked for must be checked, not assumed.
"""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_missing_device_is_refused_before_anything_is_driven(monkeypatch):
    tool = _tool('selfrun_mirror')
    monkeypatch.setattr(tool, 'attached', lambda adb, address: ['2G0YC5ZGCD03H6', 'emulator-5556'])
    monkeypatch.setattr(tool, 'reap_stale_agents', lambda: {'found': [], 'killed': []})
    record = tool.attempt(1, 3, '127.0.0.1:16416')
    assert record['exit'] == 2
    assert record['stop'] == 'the_requested_device_is_not_attached'
    assert record['events'] == 0
    assert record['reached_floor_5'] is False
    assert 'emulator-5556' in record['note']


def test_the_attached_list_is_read_from_adb(monkeypatch):
    tool = _tool('selfrun_mirror')

    class _Done:
        stdout = 'List of devices attached\n2G0YC5ZGCD03H6\tdevice\nemulator-5556\tdevice\n'

    monkeypatch.setattr(tool.subprocess, 'run', lambda *a, **k: _Done())
    assert tool.attached('adb', 'emulator-5556') == ['2G0YC5ZGCD03H6', 'emulator-5556']


def test_the_address_is_a_documented_option():
    source = (ROOT / 'tools' / 'selfrun_mirror.py').read_text(encoding='utf-8')
    assert "'--address'" in source
    assert "MAALIMBUS_ADDRESS" in source


def test_a_host_port_names_the_emulator_adb_lists(monkeypatch):
    tool = _tool('selfrun_mirror')
    assert tool._covered_by_an_emulator('127.0.0.1:5556', ['2G0YC5ZGCD03H6', 'emulator-5556']) is True
    assert tool._covered_by_an_emulator('127.0.0.1:5556', ['2G0YC5ZGCD03H6']) is False
    assert tool._covered_by_an_emulator('emulator-5556', ['emulator-5556']) is False
    assert tool._covered_by_an_emulator('127.0.0.1:notaport', ['emulator-5556']) is False


def test_the_agent_is_told_a_host_port_when_the_toolkit_names_a_serial():
    tool = _tool('selfrun_mirror')
    assert tool.agent_address('emulator-5556') == '127.0.0.1:5556'
    assert tool.agent_address('emulator-5554') == '127.0.0.1:5554'
    assert tool.agent_address('127.0.0.1:5556') == '127.0.0.1:5556'
    assert tool.agent_address('2G0YC5ZGCD03H6') == '2G0YC5ZGCD03H6'
    assert tool.agent_address('emulator-') == 'emulator-'
