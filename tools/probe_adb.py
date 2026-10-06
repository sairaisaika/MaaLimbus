"""Bounded read-only Maa capture of an already running Limbus Android app."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import cv2
from maa.controller import AdbController
from maa.define import MaaAdbInputMethodEnum, MaaAdbScreencapMethodEnum
from maa.library import Library
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job
from maalimbus.adb_device import (build, discover, foreground_of, input_policy,
                                   names)
from maalimbus.storage import write_json
from maalimbus.adb_preflight import foreground

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, default=None,
                        help='optional adb path restricting discovery; omit to let '
                             'MaaToolkit search and supply the emulator config')
    parser.add_argument('--address', required=True)
    args = parser.parse_args()
    directory = ROOT / ('evidence/runtime/adb-probe-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    # Same OS lease as Win32 and Agent; no second controller during observation.
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 45
    result = dict(pid=os.getpid(), address=args.address, input_sent=False,
                  verified_clear=False, input_method='Null', controller='Maa AdbController')
    try:
        Library.open(args.binary, agent_server=False)
        device = discover(args.address, args.adb)
        result['foreground_before'] = foreground_of(device)
        controller = build(device, input_enabled=False)
        result['device'] = device
        wait_job(controller.post_connection(), timeout=15, deadline=deadline)
        controller.set_screenshot_target_long_side(1920)
        wait_job(controller.post_screencap(), timeout=15, deadline=deadline)
        frame = controller.cached_image
        if frame is None or not frame.size or not cv2.imwrite(str(directory / 'frame.png'), frame):
            raise RuntimeError('Maa screenshot unavailable')
        result['size'] = [frame.shape[1], frame.shape[0]]
        result['foreground_after'] = foreground_of(device)
        result['reason'] = 'read_only_capture'
    except Exception as error:
        result.update(reason='probe_failed', error=str(error))
        raise
    finally:
        write_json(directory / 'result.json', result)
        print(json.dumps(dict(directory=str(directory), **result)), flush=True)
        lease.close()


if __name__ == '__main__':
    main()
