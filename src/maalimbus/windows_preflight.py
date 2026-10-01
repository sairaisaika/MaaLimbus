"""Read-only Windows process/token checks before constructing an input controller."""
import ctypes
from ctypes import wintypes
from pathlib import PureWindowsPath
import sys


class InputPermissionError(RuntimeError):
    def __init__(self, identity):
        self.identity = identity
        super().__init__('Windows blocks input from a lower-integrity controller. '
                         'Run Maa and Steam/game at matching privileges, then retry.')


def process_identity(pid):
    if sys.platform != 'win32':
        raise RuntimeError('Win32 controller requires Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    advapi.OpenProcessToken.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
    advapi.GetTokenInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                          wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    advapi.GetSidSubAuthorityCount.argtypes = (ctypes.c_void_p,)
    advapi.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    advapi.GetSidSubAuthority.argtypes = (ctypes.c_void_p, wintypes.DWORD)
    advapi.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
    class SidAttributes(ctypes.Structure):
        _fields_ = [('sid', ctypes.c_void_p), ('attributes', wintypes.DWORD)]
    process = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION only
    if not process:
        raise ctypes.WinError(ctypes.get_last_error())
    token = wintypes.HANDLE()
    try:
        name, length = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(process, 0, name, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not advapi.OpenProcessToken(process, 0x0008, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        needed = wintypes.DWORD()
        advapi.GetTokenInformation(token, 25, None, 0, ctypes.byref(needed))
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(token, 25, buffer, needed, ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(buffer, ctypes.POINTER(SidAttributes)).contents.sid
        count = advapi.GetSidSubAuthorityCount(sid).contents.value
        rid = advapi.GetSidSubAuthority(sid, count - 1).contents.value
        return {'pid': pid, 'executable': name.value, 'integrity_rid': rid}
    finally:
        if token:
            kernel.CloseHandle(token)
        kernel.CloseHandle(process)


def validate_identity(game, controller):
    if PureWindowsPath(game['executable']).name.lower() != 'limbuscompany.exe':
        raise RuntimeError('Window belongs to an unexpected process')
    identity = {'game': game, 'controller': controller, 'input_allowed':
                controller['integrity_rid'] >= game['integrity_rid']}
    if not identity['input_allowed']:
        raise InputPermissionError(identity)
    return identity


def check_window(hwnd):
    import os
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    pid = wintypes.DWORD()
    if not user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)) or not pid.value:
        raise ctypes.WinError(ctypes.get_last_error())
    return validate_identity(process_identity(pid.value), process_identity(os.getpid()))
