"""The diagnostics contract: null plus a reason, never zero, and no identifiers."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import json
import os
import subprocess

import pytest

from maalimbus import resource_diagnostics as diagnostics

SNAPSHOT_KEYS = {'version', 'sampled_at', 'interval_ms', 'cpu_percent_semantics',
                 'process_provider', 'processes', 'system', 'gpu', 'process_gpu'}
ENTRY_KEYS = {'role', 'pid', 'cpu_percent', 'rss_bytes', 'status', 'reasons'}
GPU_KEYS = {'provider', 'device_name', 'util_percent', 'vram_used_bytes', 'vram_total_bytes',
            'status', 'reasons'}
BANNED_KEYS = {'user', 'username', 'hostname', 'machine', 'machine_id', 'machineid', 'uuid',
               'serial', 'serial_number', 'command', 'cmd', 'argv', 'stdout', 'stderr',
               'executable', 'exe', 'path', 'account', 'domain'}
GPU_ROW = 'NVIDIA GeForce RTX 3070, 4, 1024, 8192\n'


def counters(kernel, user, rss=2048, reasons=None):
    return {'kernel_time_100ns': kernel, 'user_time_100ns': user, 'rss_bytes': rss,
            'reasons': dict(reasons or {})}


def system_counters(idle, kernel, user, cores=8):
    return {'idle_time_100ns': idle, 'kernel_time_100ns': kernel,
            'user_time_100ns': user, 'cores': cores}


class FakeProcesses:
    """A stub provider: no Windows, no MaaLimbus process and no device needed."""
    name = 'fake_process_counters'

    def __init__(self, discovered=(), readings=None, system=()):
        self.discovered = list(discovered)
        self.readings = {pid: list(sequence) for pid, sequence in (readings or {}).items()}
        self.system = list(system)

    def available(self):
        return True

    def discover(self):
        return list(self.discovered)

    def counters(self, pid):
        if not self.readings.get(pid):
            raise diagnostics.CounterUnavailable('process_not_found')
        return self.readings[pid].pop(0)

    def system_counters(self):
        if not self.system:
            raise diagnostics.CounterUnavailable('unsupported_platform')
        return self.system.pop(0)


class FakeGpu:
    name = 'fake_gpu_provider'

    def __init__(self, block=None):
        self.block = block or {'provider': self.name, 'device_name': 'Fake GPU', 'util_percent': 4,
                               'vram_used_bytes': 1024 * 1024, 'vram_total_bytes': 8 * 1024 * 1024,
                               'status': 'ok', 'reasons': {}}

    def read(self):
        return dict(self.block)


class FakeProcessGpu:
    name = 'fake_per_process_gpu'
    metric = 'process_utilization_percent_from_fake_provider'

    def read(self, targets):
        return [{'role': role, 'pid': pid, 'util_percent': None, 'vram_used_bytes': None,
                 'status': 'partial', 'reasons': {'util_percent': 'not_supported'}}
                for role, pid in targets]


def fake_clock(values):
    iterator = iter(values)
    return lambda: next(iterator)


def collect_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from collect_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from collect_keys(item)


def test_snapshot_carries_exactly_the_contract_fields():
    provider = FakeProcesses(readings={4242: [counters(0, 0), counters(10_000_000, 0)]},
                             system=[system_counters(0, 0, 0), system_counters(10_000_000, 10_000_000, 0)])
    snapshot = diagnostics.sample(1000, targets=[('agent', 4242)], process_provider=provider,
                                  gpu_provider=FakeGpu(), clock=fake_clock([10.0, 11.0]),
                                  sleeper=lambda seconds: None)
    assert set(snapshot) == SNAPSHOT_KEYS
    assert snapshot['version'] == diagnostics.VERSION == 1
    assert snapshot['interval_ms'] == 1000
    assert datetime.fromisoformat(snapshot['sampled_at']).tzinfo is not None
    assert set(snapshot['processes'][0]) == ENTRY_KEYS
    assert set(snapshot['system']) == {'cpu_percent', 'cores', 'status', 'reasons'}
    assert set(snapshot['gpu']) == GPU_KEYS
    assert snapshot['cpu_percent_semantics'] == diagnostics.CPU_PERCENT_SEMANTICS


def test_a_missing_process_is_null_with_a_reason_and_never_zero():
    snapshot = diagnostics.sample(1000, targets=[('agent', 4242)], process_provider=FakeProcesses(),
                                  gpu_provider=None, clock=fake_clock([0.0, 1.0]),
                                  sleeper=lambda seconds: None)
    entry = snapshot['processes'][0]
    assert entry['status'] == 'process_not_found'
    assert entry['cpu_percent'] is None and entry['rss_bytes'] is None
    assert entry['cpu_percent'] != 0 and entry['rss_bytes'] != 0
    assert entry['reasons'] == {'pid': 'process_not_found', 'cpu_percent': 'process_not_found',
                                'rss_bytes': 'process_not_found'}


def test_cpu_percent_is_one_busy_core_at_one_hundred_and_may_exceed_it():
    provider = FakeProcesses(readings={1: [counters(0, 0), counters(10_000_000, 0)],
                                       2: [counters(0, 0), counters(25_000_000, 0)]})
    snapshot = diagnostics.sample(1000, targets=[('app', 1), ('runner', 2)], process_provider=provider,
                                  gpu_provider=None, clock=fake_clock([5.0, 6.0]),
                                  sleeper=lambda seconds: None)
    assert [entry['cpu_percent'] for entry in snapshot['processes']] == [100.0, 250.0]
    assert 'one fully busy core' in snapshot['cpu_percent_semantics']
    assert 'one fully busy core' in diagnostics.__doc__


def test_the_machine_reference_uses_the_same_normalization():
    provider = FakeProcesses(readings={1: [counters(0, 0), counters(0, 0)]},
                             system=[system_counters(0, 0, 0), system_counters(10_000_000, 10_000_000, 25_000_000)])
    snapshot = diagnostics.sample(1000, targets=[('app', 1)], process_provider=provider,
                                  gpu_provider=None, clock=fake_clock([0.0, 1.0]),
                                  sleeper=lambda seconds: None)
    assert snapshot['system'] == {'cpu_percent': 250.0, 'cores': 8, 'status': 'ok', 'reasons': {}}


def test_no_identifier_like_or_raw_command_field_is_exported():
    provider = FakeProcesses(discovered=[('agent', 1)],
                             readings={1: [counters(0, 0), counters(10_000_000, 0)]},
                             system=[system_counters(0, 0, 0), system_counters(5_000_000, 5_000_000, 0)])
    snapshot = diagnostics.sample(1000, process_provider=provider, gpu_provider=FakeGpu(),
                                  process_gpu_provider=FakeProcessGpu(),
                                  clock=fake_clock([0.0, 1.0]), sleeper=lambda seconds: None)
    text = json.dumps(snapshot, sort_keys=True)
    assert '--query-gpu' not in text and '--format=csv' not in text
    assert '\\' not in text and '/Users/' not in text
    username = os.environ.get('USERNAME') or os.environ.get('USER') or ''
    if len(username) > 2:
        assert username.lower() not in text.lower()
    for key in collect_keys(snapshot):
        assert key.lower() not in BANNED_KEYS


def test_no_gpu_provider_is_unsupported_rather_than_zero_or_a_stolen_figure():
    snapshot = diagnostics.sample(1000, targets=[('agent', 1)],
                                  process_provider=FakeProcesses(
                                      readings={1: [counters(0, 0), counters(0, 0)]}),
                                  gpu_provider=None, clock=fake_clock([0.0, 1.0]),
                                  sleeper=lambda seconds: None)
    gpu = snapshot['gpu']
    assert gpu['status'] == 'unsupported' and gpu['provider'] is None
    assert all(gpu[field] is None for field in
               ('device_name', 'util_percent', 'vram_used_bytes', 'vram_total_bytes'))
    process_gpu = snapshot['process_gpu']
    assert process_gpu['status'] == 'unsupported'
    assert process_gpu['reason'] == 'no_per_process_gpu_provider'
    assert process_gpu['metric'] is None and process_gpu['samples'] == []


def test_a_bounded_gpu_timeout_is_reported_without_raising(monkeypatch):
    def explode(*args, **kwargs):
        raise subprocess.TimeoutExpired('nvidia-smi', 3.0)
    monkeypatch.setattr(diagnostics.subprocess, 'run', explode)
    block = diagnostics.NvidiaSmiProvider().read()
    assert block['status'] == 'timeout' and block['provider'] == 'nvidia-smi'
    assert block['util_percent'] is None and block['vram_used_bytes'] is None
    assert set(block['reasons'].values()) == {'timeout'}


def test_a_missing_gpu_provider_is_a_normal_result(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError
    monkeypatch.setattr(diagnostics.subprocess, 'run', missing)
    assert diagnostics.NvidiaSmiProvider().read()['status'] == 'provider_missing'


def test_the_gpu_query_is_a_fixed_argv_with_a_timeout_and_reads_mebibytes(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        return SimpleNamespace(returncode=0, stdout=GPU_ROW)
    monkeypatch.setattr(diagnostics.subprocess, 'run', fake_run)
    block = diagnostics.NvidiaSmiProvider(timeout_s=2.5).read()
    assert seen['command'] == ['nvidia-smi',
                               '--query-gpu=name,utilization.gpu,memory.used,memory.total',
                               '--format=csv,noheader,nounits']
    assert seen['kwargs']['timeout'] == 2.5 and 'shell' not in seen['kwargs']
    assert block['status'] == 'ok' and block['reasons'] == {}
    assert block['device_name'] == 'NVIDIA GeForce RTX 3070' and block['util_percent'] == 4
    assert block['vram_used_bytes'] == 1024 * diagnostics._MEBIBYTE
    assert block['vram_total_bytes'] == 8192 * diagnostics._MEBIBYTE


def test_a_fake_gpu_provider_path_needs_no_nvidia_gpu():
    snapshot = diagnostics.sample(1000, targets=[('agent', 1)],
                                  process_provider=FakeProcesses(
                                      readings={1: [counters(0, 0), counters(0, 0)]}),
                                  gpu_provider=FakeGpu(), clock=fake_clock([0.0, 1.0]),
                                  sleeper=lambda seconds: None)
    assert snapshot['gpu']['status'] == 'ok'
    assert snapshot['gpu']['device_name'] == 'Fake GPU' and snapshot['gpu']['util_percent'] == 4


def test_per_process_gpu_figures_are_labelled_and_never_the_whole_device_number():
    snapshot = diagnostics.sample(1000, targets=[('agent', 7)],
                                  process_provider=FakeProcesses(
                                      readings={7: [counters(0, 0), counters(0, 0)]}),
                                  gpu_provider=FakeGpu(), process_gpu_provider=FakeProcessGpu(),
                                  clock=fake_clock([0.0, 1.0]), sleeper=lambda seconds: None)
    block = snapshot['process_gpu']
    assert block['provider'] == 'fake_per_process_gpu'
    assert block['metric'] == 'process_utilization_percent_from_fake_provider'
    assert block['samples'][0]['pid'] == 7
    assert block['samples'][0]['util_percent'] is None
    assert block['samples'][0]['util_percent'] != snapshot['gpu']['util_percent']


def test_an_unavailable_platform_is_a_normal_result_not_an_error(monkeypatch):
    provider = FakeProcesses()
    monkeypatch.setattr(provider, 'available', lambda: False)
    snapshot = diagnostics.sample(1000, process_provider=provider, gpu_provider=None,
                                  clock=fake_clock([0.0, 1.0]), sleeper=lambda seconds: None)
    assert snapshot['process_provider']['status'] == 'unsupported'
    assert snapshot['process_provider']['reason'] == 'unsupported_platform'
    assert snapshot['system']['status'] == 'unsupported_platform'
    assert snapshot['system']['cpu_percent'] is None and snapshot['system']['cores'] is None


def test_the_interval_is_bounded_and_the_default_is_one_shot():
    with pytest.raises(ValueError):
        diagnostics.sample(0, targets=[], process_provider=FakeProcesses())
    with pytest.raises(ValueError):
        diagnostics.sample(diagnostics.MAX_INTERVAL_MS + 1, targets=[],
                           process_provider=FakeProcesses())
    slept = []
    snapshot = diagnostics.sample(250, targets=[], process_provider=FakeProcesses(),
                                  gpu_provider=None, clock=fake_clock([0.0, 0.25]),
                                  sleeper=slept.append)
    assert slept == [0.25] and snapshot['interval_ms'] == 250


def test_the_sampler_has_no_controller_reference_and_no_new_dependency():
    source = Path(diagnostics.__file__).read_text(encoding='utf-8')
    for banned in ('psutil', 'pynvml', 'controller_lease', 'controller.lock', 'requests',
                   'urllib', 'shell=True', 'evidence/', 'config/'):
        assert banned not in source
