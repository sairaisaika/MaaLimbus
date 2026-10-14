"""Bounded, read-only CPU/RAM/GPU sampling for the local diagnostics panel.

``cpu_percent`` is normalized so that 100.0 is one fully busy core; a process
whose threads run on several cores at once can exceed 100 (250.0 means two and a
half cores of load). The machine reference in ``system`` follows the same rule,
so it can reach ``cores * 100``. Every snapshot repeats the rule verbatim as
``cpu_percent_semantics``.

An unknown value is null together with a short machine-readable reason; it is
never zero and never a guess. Missing, stopped and unsupported providers are
normal results: the snapshot still prints, with the provider's own status and
reasons.

The sampler is independent of the controller. It takes no lock, never reads the
controller lease and writes no state. On Windows it reads process and system
counters through ctypes (GetProcessTimes, GetProcessMemoryInfo, GetSystemTimes)
and asks an NVIDIA GPU only through a bounded ``nvidia-smi`` subprocess with a
hard timeout and no elevation; that call is a fixed argument list, never a shell
and never a raw command string in the output. Per-process GPU figures are only
emitted by a provider that can attribute them, and the snapshot says
``unsupported`` when none exists instead of reusing the whole-GPU figure as if
it were the application's. No username, hostname, machine id, serial number,
UUID, full command line or raw provider output is exported, and nothing is
uploaded.
"""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import os
import subprocess
import sys
import time

VERSION = 1
MIN_INTERVAL_MS = 1
MAX_INTERVAL_MS = 60000
DEFAULT_INTERVAL_MS = 1000
GPU_TIMEOUT_S = 3.0
CPU_PERCENT_SEMANTICS = '100 = one fully busy core; multi-threaded processes may exceed 100'
_QUERY_LIMITED_INFORMATION = 0x1000
_PROCESS_VM_READ = 0x0010
_TH32CS_SNAPPROCESS = 0x2
_CREATE_NO_WINDOW = 0x08000000
_TICKS_PER_SECOND = 10_000_000
_MEBIBYTE = 1024 * 1024
_DEFAULT_PROVIDER = object()

#: Executable basename (lowercase) -> the role reported for that process. Only a
#: known role is exported; the executable name itself and its path never are.
PROCESS_ROLES = {'maalimbus.exe': 'app', 'maalimbuslauncher.exe': 'launcher',
                 'maalimbusagent.exe': 'agent', 'maalimbusrunner.exe': 'runner'}
#: ``nvidia-smi`` flags for the one bounded whole-device query (never a command string).
GPU_QUERY = ('--query-gpu=name,utilization.gpu,memory.used,memory.total',
             '--format=csv,noheader,nounits')
_GPU_METRICS = ('device_name', 'util_percent', 'vram_used_bytes', 'vram_total_bytes')


class CounterUnavailable(RuntimeError):
    """A counter could not be read; the reason is a short machine-readable token."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]


class _ProcessEntry32(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_void_p),
                ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_wchar * 260)]


def _apis():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.GetProcessTimes.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                       ctypes.POINTER(wintypes.FILETIME),
                                       ctypes.POINTER(wintypes.FILETIME),
                                       ctypes.POINTER(wintypes.FILETIME))
    kernel.GetSystemTimes.argtypes = (ctypes.POINTER(wintypes.FILETIME),
                                      ctypes.POINTER(wintypes.FILETIME),
                                      ctypes.POINTER(wintypes.FILETIME))
    psapi.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE,
                                           ctypes.POINTER(_ProcessMemoryCounters), wintypes.DWORD)
    return kernel, psapi


def _reason_for_error(error):
    if error == 5:return 'access_denied'
    if error in (6,87,1168):return 'process_not_found'
    return 'query_failed'


def _ticks(filetime):
    return (filetime.dwHighDateTime << 32) | filetime.dwLowDateTime


def _machine_busy(counters):
    """Busy 100ns ticks; GetSystemTimes' kernel time already includes the idle time."""
    return counters['kernel_time_100ns'] + counters['user_time_100ns'] - counters['idle_time_100ns']


def _read(provider, method, *args):
    """Return ``(value, reason)``; a missing provider and a failed read are data, not errors."""
    if provider is None:
        return None, 'unsupported_platform'
    try:
        return getattr(provider, method)(*args), None
    except CounterUnavailable as error:
        return None, error.reason
    except Exception:
        return None, 'query_failed'


class WindowsProcessProvider:
    """Read-only Windows process and system counters through ctypes.

    It opens processes with PROCESS_QUERY_LIMITED_INFORMATION only (never
    elevation, never a debug or input right), reads what the kernel reports and
    closes every handle. Nothing is written and no other program is started.
    """
    name = 'windows_process_counters'

    def available(self):
        return sys.platform == 'win32'

    def discover(self):
        """Known MaaLimbus processes as ``(role, pid)``; unknown names are skipped, not guessed."""
        if not self.available():
            raise CounterUnavailable('unsupported_platform')
        kernel, _ = _apis()
        kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
        kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ProcessEntry32))
        kernel.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ProcessEntry32))
        snapshot = kernel.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
        if not snapshot or snapshot == ctypes.c_void_p(-1).value:
            raise CounterUnavailable('snapshot_failed')
        found, entry = [], _ProcessEntry32()
        entry.dwSize = ctypes.sizeof(_ProcessEntry32)
        try:
            following = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            while following:
                role = PROCESS_ROLES.get(str(entry.szExeFile).lower())
                if role:found.append((role, int(entry.th32ProcessID)))
                following = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel.CloseHandle(snapshot)
        return sorted(set(found))

    def _open(self, kernel, pid, access):
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            raise CounterUnavailable('invalid_pid')
        handle = kernel.OpenProcess(access, False, pid)
        if not handle:
            raise CounterUnavailable(_reason_for_error(ctypes.get_last_error()))
        return handle

    def counters(self, pid):
        if not self.available():
            raise CounterUnavailable('unsupported_platform')
        kernel, psapi = _apis()
        handle = self._open(kernel, pid, _QUERY_LIMITED_INFORMATION)
        reasons = {}
        try:
            created, exited = wintypes.FILETIME(), wintypes.FILETIME()
            kernel_time, user_time = wintypes.FILETIME(), wintypes.FILETIME()
            if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                          ctypes.byref(kernel_time), ctypes.byref(user_time)):
                raise CounterUnavailable(_reason_for_error(ctypes.get_last_error()))
            rss = self._rss(kernel, psapi, handle, pid)
            if rss is None:reasons['rss_bytes'] = 'access_denied'
            return {'kernel_time_100ns': _ticks(kernel_time), 'user_time_100ns': _ticks(user_time),
                    'rss_bytes': rss, 'reasons': reasons}
        finally:
            kernel.CloseHandle(handle)

    def _rss(self, kernel, psapi, handle, pid):
        memory = _ProcessMemoryCounters()
        memory.cb = ctypes.sizeof(_ProcessMemoryCounters)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
            return int(memory.WorkingSetSize)
        retry = None
        try:  # the documented access set for this call; refused processes stay unknown
            retry = self._open(kernel, pid, _QUERY_LIMITED_INFORMATION | _PROCESS_VM_READ)
            if psapi.GetProcessMemoryInfo(retry, ctypes.byref(memory), memory.cb):
                return int(memory.WorkingSetSize)
            return None
        except CounterUnavailable:
            return None
        finally:
            if retry:kernel.CloseHandle(retry)

    def system_counters(self):
        """Machine reference: idle, kernel (idle included) and user time in 100ns ticks."""
        if not self.available():
            raise CounterUnavailable('unsupported_platform')
        kernel, _ = _apis()
        idle, kernel_time, user_time = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        if not kernel.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel_time), ctypes.byref(user_time)):
            raise CounterUnavailable(_reason_for_error(ctypes.get_last_error()))
        return {'idle_time_100ns': _ticks(idle), 'kernel_time_100ns': _ticks(kernel_time),
                'user_time_100ns': _ticks(user_time), 'cores': os.cpu_count()}


class NvidiaSmiProvider:
    """One bounded whole-device GPU query; fixed argv, hard timeout, no elevation."""
    name = 'nvidia-smi'

    def __init__(self, timeout_s=GPU_TIMEOUT_S, executable='nvidia-smi'):
        self.timeout_s = timeout_s
        self.executable = executable

    def read(self):
        block = {'provider': self.name, 'device_name': None, 'util_percent': None,
                 'vram_used_bytes': None, 'vram_total_bytes': None, 'status': 'ok', 'reasons': {}}
        command = [self.executable, *GPU_QUERY]
        creation = _CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False,
                                    timeout=self.timeout_s, creationflags=creation)
        except FileNotFoundError:
            return _gpu_failure(block, 'provider_missing')
        except subprocess.TimeoutExpired:
            return _gpu_failure(block, 'timeout')
        except OSError:
            return _gpu_failure(block, 'provider_error')
        if result.returncode != 0:
            return _gpu_failure(block, 'provider_error')
        rows = [line.strip() for line in (result.stdout or '').splitlines() if line.strip()]
        if not rows:
            return _gpu_failure(block, 'no_device')
        fields = [field.strip() for field in rows[0].split(',')]
        if len(fields) != 4:
            return _gpu_failure(block, 'unparsable_output')
        block['device_name'] = fields[0] or None
        if not block['device_name']:block['reasons']['device_name'] = 'unavailable'
        block['util_percent'] = _gpu_percent(fields[1], block['reasons'], 'util_percent')
        block['vram_used_bytes'] = _gpu_mebibytes(fields[2], block['reasons'], 'vram_used_bytes')
        block['vram_total_bytes'] = _gpu_mebibytes(fields[3], block['reasons'], 'vram_total_bytes')
        if block['reasons']:block['status'] = 'partial'
        return block


def _gpu_failure(block, reason, status=None):
    block['status'] = status or reason
    block['reasons'] = {key: reason for key in _GPU_METRICS}
    return block


def _gpu_percent(text, reasons, key):
    if not text or text.startswith('['):
        reasons[key] = 'not_supported'
        return None
    try:
        return int(text)
    except ValueError:
        reasons[key] = 'unparsable'
        return None


def _gpu_mebibytes(text, reasons, key):
    value = _gpu_percent(text, reasons, key)
    return None if value is None else value * _MEBIBYTE


def _process_sample(role, pid, before, after, elapsed):
    reasons = {}
    if before[0] is None or after[0] is None:
        status = after[1] or before[1] or 'query_failed'
        return {'role': role, 'pid': pid, 'cpu_percent': None, 'rss_bytes': None,
                'status': status, 'reasons': {'pid': status, 'cpu_percent': status,
                                              'rss_bytes': status}}
    cpu_percent = None
    ticks = (after[0]['user_time_100ns'] + after[0]['kernel_time_100ns']
             - before[0]['user_time_100ns'] - before[0]['kernel_time_100ns'])
    if ticks < 0:
        reasons['cpu_percent'] = 'counter_reset'
    else:
        cpu_percent = round(ticks / _TICKS_PER_SECOND / elapsed * 100, 2)
    rss_bytes = after[0].get('rss_bytes')
    if rss_bytes is None:
        reasons['rss_bytes'] = (after[0].get('reasons', {}).get('rss_bytes')
                                or before[0].get('reasons', {}).get('rss_bytes')
                                or 'unavailable')
    return {'role': role, 'pid': pid, 'cpu_percent': cpu_percent, 'rss_bytes': rss_bytes,
            'status': 'ok' if not reasons else 'partial', 'reasons': reasons}


def _system_sample(before, after, elapsed, cores):
    reasons = {}
    cpu_percent = None
    if before[0] is None or after[0] is None:
        status = after[1] or before[1] or 'query_failed'
        return {'cpu_percent': None, 'cores': None, 'status': status,
                'reasons': {'cpu_percent': status, 'cores': status}}
    cores = after[0].get('cores') or cores
    ticks = _machine_busy(after[0]) - _machine_busy(before[0])
    if ticks < 0:
        reasons['cpu_percent'] = 'counter_reset'
    else:
        cpu_percent = round(ticks / _TICKS_PER_SECOND / elapsed * 100, 2)
    return {'cpu_percent': cpu_percent, 'cores': cores,
            'status': 'ok' if not reasons else 'partial', 'reasons': reasons}


def _gpu_block(provider):
    if provider is None:
        block = {'provider': None, 'device_name': None, 'util_percent': None,
                 'vram_used_bytes': None, 'vram_total_bytes': None, 'status': 'unsupported',
                 'reasons': {}}
        return _gpu_failure(block, 'no_gpu_provider', status='unsupported')
    try:
        return provider.read()
    except Exception:
        return _gpu_failure({}, 'provider_error')


def _process_gpu_block(provider, targets):
    """Optional attributable per-process GPU figures; ``unsupported`` is the honest default."""
    if provider is None:
        return {'provider': None, 'metric': None, 'status': 'unsupported',
                'reason': 'no_per_process_gpu_provider', 'samples': []}
    name = getattr(provider, 'name', None)
    metric = getattr(provider, 'metric', None)
    try:
        raw = provider.read([(role, pid) for role, pid in targets])
    except Exception:
        return {'provider': name, 'metric': metric, 'status': 'provider_error',
                'reason': 'provider_error', 'samples': []}
    samples = []
    for item in raw:
        reasons = dict(item.get('reasons') or {})
        samples.append({'role': item.get('role'), 'pid': item.get('pid'),
                        'util_percent': item.get('util_percent'),
                        'vram_used_bytes': item.get('vram_used_bytes'),
                        'status': item.get('status', 'ok') if not reasons else 'partial',
                        'reasons': reasons})
    return {'provider': name, 'metric': metric, 'status': 'ok', 'reason': None, 'samples': samples}


def sample(interval_ms=DEFAULT_INTERVAL_MS, *, targets=None, process_provider=_DEFAULT_PROVIDER,
           gpu_provider=_DEFAULT_PROVIDER, process_gpu_provider=None, clock=None, sleeper=None):
    """One bounded snapshot.

    The window is the requested ``interval_ms`` for the wall-clock denominator and
    a real bounded sleep of that length between the two counter reads. Providers
    are injectable so a machine without an NVIDIA GPU (or without Windows) still
    produces the full contract from fakes; ``None`` means "no such provider" and
    yields the unsupported states rather than an error.
    """
    if (not isinstance(interval_ms, int) or isinstance(interval_ms, bool)
            or not MIN_INTERVAL_MS <= interval_ms <= MAX_INTERVAL_MS):
        raise ValueError(f'interval_ms must be an integer in {MIN_INTERVAL_MS}..{MAX_INTERVAL_MS}')
    if process_provider is _DEFAULT_PROVIDER:process_provider = WindowsProcessProvider()
    if gpu_provider is _DEFAULT_PROVIDER:gpu_provider = NvidiaSmiProvider()
    clock = clock or time.monotonic
    sleeper = sleeper or time.sleep
    available = process_provider is not None and bool(
        getattr(process_provider, 'available', lambda: True)())
    provider_name = getattr(process_provider, 'name', None) or 'unsupported'
    if targets is not None:
        selected = [(str(role), int(pid)) for role, pid in targets]
    elif available:
        discovered, _ = _read(process_provider, 'discover')
        selected = sorted(set(discovered or []))
        if not any(pid == os.getpid() for _, pid in selected):selected.append(('sampler', os.getpid()))
    else:
        selected = []
    before = {pid: _read(process_provider, 'counters', pid) for _, pid in selected}
    system_before = _read(process_provider, 'system_counters')
    started = clock()
    sleeper(interval_ms / 1000.0)
    elapsed = max(clock() - started, 1e-6)
    after = {pid: _read(process_provider, 'counters', pid) for _, pid in selected}
    system_after = _read(process_provider, 'system_counters')
    processes = [_process_sample(role, pid, before[pid], after[pid], elapsed) for role, pid in selected]
    return {
        'version': VERSION,
        'sampled_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'interval_ms': interval_ms,
        'cpu_percent_semantics': CPU_PERCENT_SEMANTICS,
        'process_provider': {'provider': provider_name,
                             'status': 'ok' if available else 'unsupported',
                             'reason': None if available else 'unsupported_platform',
                             'sampled': len(selected)},
        'processes': processes,
        'system': _system_sample(system_before, system_after, elapsed, os.cpu_count()),
        'gpu': _gpu_block(gpu_provider),
        'process_gpu': _process_gpu_block(process_gpu_provider, selected),
    }
