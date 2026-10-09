"""Copy the updater outside the app, update while closed, then open native MXU."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from maalimbus.controller_lease import ControllerLease
from maalimbus.startup_update import startup_update, check_project_update
from maalimbus.update_install import closed_app, install_staged, plain_path, plain_tree, metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path)
    parser.add_argument('--parent', type=int)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    executable = plain_path(sys.executable)
    if args.check_only:
        if args.app is None and not getattr(sys,'frozen',False):
            parser.error('Source check requires --app')
        app=plain_path(args.app or executable.parents[1])
        check_project_update(app)
        return
    if args.app is None:
        if not getattr(sys, 'frozen', False):
            parser.error('Source launcher requires --app')
        app = executable.parents[1]
        metadata(app)
        plain_tree(executable.parent)
        copied = app.parent/('.maalimbus-launcher-'+uuid.uuid4().hex)
        shutil.copytree(executable.parent, copied)
        subprocess.Popen([str(copied/executable.name), '--app', str(app), '--parent', str(os.getpid())],
                         cwd=copied, creationflags=0x08000000)
        return
    app = plain_path(args.app)
    if app == executable.parent or app in executable.parents:
        raise ValueError('Launcher must run outside the app being updated')
    metadata(app)
    # Only observe our known bootstrap parent until it exits. Never kill/restart it.
    if args.parent:
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x100000, False, args.parent)
        if handle:
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            try:
                if kernel.WaitForSingleObject(handle, 20000) != 0:
                    raise ValueError('Bootstrap still active')
            finally:
                kernel.CloseHandle(handle)
    work = app.parent/'.maalimbus-startup'
    lease = ControllerLease(work/'launcher.lock')
    try:
        process_check = lambda target: closed_app(target, external_launcher_pid=os.getpid())
        process_check(app)
        installer = lambda staged, target: install_staged(staged, target, work/'controller.lock',
                                                        process_check=process_check)
        startup_update(app, work, install=installer)
        process_check(app)
        # Official unmodified MXU owns any standard Windows UAC prompt.
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen([str(app/'MaaLimbus.exe')], cwd=app, startupinfo=startup)
    finally:
        lease.close()


if __name__ == '__main__':
    main()
