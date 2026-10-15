"""The launcher's resource-diagnostics bridge: read-only, no lease, no launch.

This is the deviceless half of the MXU bridge check. It runs the same entry point
the Tauri command runs (`MaaLimbusLauncher.exe --resource-diagnostics`) from
source, with the controller lease and the client launch boobytrapped, and asserts
that one honest sampler snapshot comes back on stdout.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from maalimbus import resource_diagnostics
from maalimbus.runtime_paths import ROOT

SNAPSHOT_KEYS = {'version', 'sampled_at', 'interval_ms', 'cpu_percent_semantics',
                 'process_provider', 'processes', 'system', 'gpu', 'process_gpu'}
BANNED_KEYS = {'user', 'username', 'hostname', 'machine', 'machine_id', 'uuid', 'serial',
               'serial_number', 'command', 'cmd', 'argv', 'executable', 'exe', 'path',
               'account', 'domain'}


def load_launcher():
    spec = importlib.util.spec_from_file_location('test_diagnostics_launcher',
                                                  ROOT/'tools/launch_app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeGpu:
    name = 'fake_gpu_provider'

    def __init__(self, *args, **kwargs):
        pass

    def read(self):
        return {'provider': self.name, 'device_name': 'Fake GPU', 'util_percent': 7,
                'vram_used_bytes': 3 * 1024 * 1024, 'vram_total_bytes': 16 * 1024 * 1024,
                'status': 'ok', 'reasons': {}}


@pytest.fixture
def launcher(monkeypatch):
    module = load_launcher()

    class ForbiddenLease:
        def __init__(self, *args, **kwargs):
            pytest.fail('resource diagnostics must not take the controller lease')

    monkeypatch.setattr(module, 'ControllerLease', ForbiddenLease)
    monkeypatch.setattr(module, 'startup_update', lambda *a, **k: pytest.fail('must not update'))
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: pytest.fail('must not launch'))
    monkeypatch.setattr(resource_diagnostics, 'NvidiaSmiProvider', FakeGpu)
    return module


def test_the_bridge_returns_one_honest_snapshot_without_lease_or_launch(launcher, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['launcher', '--resource-diagnostics', '--interval-ms', '1'])
    launcher.main()
    snapshot = json.loads(capsys.readouterr().out)
    assert set(snapshot) == SNAPSHOT_KEYS
    assert snapshot['version'] == resource_diagnostics.VERSION
    assert snapshot['interval_ms'] == 1
    assert snapshot['gpu']['device_name'] == 'Fake GPU' and snapshot['gpu']['util_percent'] == 7
    assert snapshot['cpu_percent_semantics'] == resource_diagnostics.CPU_PERCENT_SEMANTICS
    assert snapshot['process_gpu']['reason'] == 'no_per_process_gpu_provider'
    assert snapshot['process_gpu']['samples'] == []


def test_the_bridge_exports_no_identifier_like_or_raw_command_field(launcher, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['launcher', '--resource-diagnostics', '--interval-ms', '1'])
    launcher.main()
    text = capsys.readouterr().out
    assert '--query-gpu' not in text and '--format=csv' not in text
    assert str(ROOT) not in text and '\\' not in text
    for key in _keys(json.loads(text)):
        assert key.lower() not in BANNED_KEYS


def _keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def test_the_bridge_defaults_to_the_sampler_window_and_refuses_a_bad_one(launcher, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['launcher', '--resource-diagnostics'])
    launcher.main()
    assert json.loads(capsys.readouterr().out)['interval_ms'] == resource_diagnostics.DEFAULT_INTERVAL_MS
    monkeypatch.setattr('sys.argv', ['launcher', '--resource-diagnostics', '--interval-ms', '0'])
    with pytest.raises(ValueError, match='interval_ms must be an integer'):
        launcher.main()


def test_diagnostics_cannot_be_combined_with_an_update_or_a_launch(launcher, monkeypatch):
    monkeypatch.setattr('sys.argv', ['launcher', '--resource-diagnostics', '--check-only'])
    with pytest.raises(SystemExit):
        launcher.main()
    monkeypatch.setattr('sys.argv', ['launcher', '--resource-diagnostics', '--skip-team', 'a'*32])
    with pytest.raises(SystemExit):
        launcher.main()


def test_the_panel_source_and_its_tests_are_part_of_the_tracked_overlay():
    """The overlay is the source of truth; the patch tool copies it into MXU."""
    patch = (ROOT/'tools/patch_mxu_client.py').read_text(encoding='utf8')
    assert 'ResourceDiagnosticsPanel.tsx' in patch
    assert 'limbus_diagnostics.rs' in patch
    assert (ROOT/'desktop/mxu/ResourceDiagnosticsPanel.tsx').is_file()
    assert (ROOT/'desktop/mxu/resourceDiagnostics.ts').is_file()
    assert (ROOT/'desktop/mxu/resourceDiagnostics.test.mjs').is_file()
    assert (ROOT/'desktop/mxu/limbus_diagnostics.rs').is_file()
