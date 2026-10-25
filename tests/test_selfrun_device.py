"""D168: the run is told which device to drive, and it checks before it drives.

On 2026-10-25 two devices were attached (`2G0YC5ZGCD03H6` and `emulator-5556`), the
framework picked the physical phone by itself, and the attempt wrote zero events and read
like a crash.  An address that is asked for must be checked, not assumed.
"""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _probe():
    import sys
    sys.path.insert(0, str(ROOT / 'src'))
    from maalimbus import agent_probe
    return agent_probe


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


def test_an_agent_that_dies_in_start_up_is_reported(monkeypatch):
    tool = _tool('selfrun_mirror')

    class _Done:
        returncode = 1073741845
        stdout = ''
        stderr = 'OSError: [WinError 1073741845]\nAssertion failed: Socket operation on non-socket'

    monkeypatch.setattr(tool.subprocess, 'run', lambda *a, **k: _Done())
    verdict = tool.agent_survives_start_up(ROOT / 'dist' / 'MaaLimbus' / 'agent' / 'MaaLimbusAgent.exe')
    assert verdict['survived'] is False
    assert verdict['exit'] == 1073741845
    assert 'non-socket' in verdict['tail']


def test_an_agent_still_running_when_the_probe_gives_up_has_passed(monkeypatch):
    tool = _tool('selfrun_mirror')

    def _timeout(*a, **k):
        raise tool.subprocess.TimeoutExpired(cmd='agent', timeout=1)

    monkeypatch.setattr(tool.subprocess, 'run', _timeout)
    verdict = tool.agent_survives_start_up(ROOT / 'dist' / 'MaaLimbus' / 'agent' / 'MaaLimbusAgent.exe')
    assert verdict['survived'] is True
    assert verdict['exit'] is None


def test_a_missing_agent_binary_is_not_a_crash(monkeypatch):
    tool = _tool('selfrun_mirror')

    def _oserror(*a, **k):
        raise OSError('no such file')

    monkeypatch.setattr(tool.subprocess, 'run', _oserror)
    verdict = tool.agent_survives_start_up(ROOT / 'nope.exe')
    assert verdict['survived'] is False
    assert 'no such file' in verdict['tail']


def test_one_owner_answers_whether_the_agent_starts(monkeypatch):
    probe = _probe()
    tool = _tool('selfrun_mirror')
    called = {}

    def _probe_call(agent, seconds=8.0):
        called['agent'] = str(agent)
        return {'survived': True, 'exit': None, 'tail': 'ok', 'agent': str(agent)}

    monkeypatch.setattr(probe, 'probe', _probe_call)
    verdict = tool.agent_survives_start_up(ROOT / 'dist' / 'MaaLimbus' / 'agent' / 'MaaLimbusAgent.exe')
    assert verdict['survived'] is True
    assert called['agent'].endswith('MaaLimbusAgent.exe')


def test_the_failure_class_is_named_from_the_process_own_words():
    probe = _probe()
    zmq = {'survived': False, 'exit': 1073741845,
           'tail': 'failed | Assertion failed: Socket operation on non-socket [10038]'}
    assert probe.classify(zmq) == 'ipc_socket_unavailable'
    assert probe.classify({'survived': True, 'exit': None, 'tail': 'ok'}) == 'started'
    assert probe.classify({'survived': False, 'exit': None, 'tail': 'no such file'}) == 'missing_binary'
    assert probe.classify({'survived': False, 'exit': 1, 'tail': 'ImportError: x'}) == 'python_startup_error'
    assert probe.classify({'survived': False, 'exit': 1, 'tail': ''}) == 'unknown_failure'
