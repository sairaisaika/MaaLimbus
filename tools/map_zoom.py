"""Zoom the Mirror Dungeon map view with Maa's own simulated touch.

The map screen can be pinched like any other touch surface, and the user asked for the
view to be zoomed out so the whole floor is visible before the run walks on
(m10541: "你现在走下面那条路，你可以把地图缩小校准然后继续往下走"). A pinch is a
gesture that changes no game state -- it is not a click on any control -- but it is
still live input, so it goes through the same authorization gate as every other tool
here, and through Maa so MuMu only ever sees simulated touch.

Usage:

    python tools/map_zoom.py --binary <dir with MaaFramework.dll> \\
        --address 127.0.0.1:16416 --authorize <nonce> [--factor 0.55] [--radius 300]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))

import cv2  # noqa: E402
from maa.library import Library  # noqa: E402
from maa.toolkit import Toolkit  # noqa: E402

from maalimbus.adb_device import build, discover, input_policy  # noqa: E402
from maalimbus.controller_lease import ControllerLease  # noqa: E402
from maalimbus.jobs import wait_job  # noqa: E402
from window_step import AUTHORIZATION, authorized, prepare  # noqa: E402


def screencap(address: str, adb: str | None, path: Path) -> bool:
    """One read-only frame through adb; no Maa input involved."""
    import subprocess
    adb = adb or 'adb'
    result = subprocess.run([adb, '-s', address, 'exec-out', 'screencap', '-p'],
                            capture_output=True)
    if result.returncode != 0 or not result.stdout:
        return False
    path.write_bytes(result.stdout)
    return True


def pinch(controller, centre, radius, factor, seconds=0.9):
    """Two simulated fingers closing towards each other; returns the point pairs sent."""
    cx, cy = centre
    left = (cx - radius, cy)
    right = (cx + radius, cy)
    target = max(40, int(radius * factor))
    steps = 12
    sent = []
    wait_job(controller.post_touch_down(left[0], left[1], 0), timeout=10)
    wait_job(controller.post_touch_down(right[0], right[1], 1), timeout=10)
    for index in range(1, steps + 1):
        offset = radius - (radius - target) * index / steps
        wait_job(controller.post_touch_move(int(cx - offset), cy, 0), timeout=10)
        wait_job(controller.post_touch_move(int(cx + offset), cy, 1), timeout=10)
        sent.append((int(cx - offset), int(cx + offset)))
        time.sleep(seconds / steps)
    wait_job(controller.post_touch_up(0), timeout=10)
    wait_job(controller.post_touch_up(1), timeout=10)
    return sent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, help='directory holding MaaFramework.dll')
    parser.add_argument('--address', required=True, help='adb address, e.g. 127.0.0.1:16416')
    parser.add_argument('--authorize', required=True, help='the nonce named in the authorization file')
    parser.add_argument('--adb', default=None, help='adb executable; defaults to adb on PATH')
    parser.add_argument('--factor', type=float, default=0.55,
                        help='final radius as a fraction of the start radius; smaller zooms out more')
    parser.add_argument('--radius', type=int, default=320, help='start half-distance in pixels')
    parser.add_argument('--centre', default='960,540', help='gesture centre as x,y in device pixels')
    parser.add_argument('--report', default='build/map-zoom.json')
    parser.add_argument('--click', default='',
                        help='instead of a pinch, send exactly one click at 1920-space X,Y '
                             '(the space Maa clicks in, proven by map_probe_one_node); a '
                             'calibration click still needs this same authorization')
    args = parser.parse_args()

    if not authorized(args.authorize):
        print(json.dumps({'refused': 'authorization_does_not_name_this_nonce',
                          'hint': f'{AUTHORIZATION} must grant live_input_authorized with this nonce'},
                         ensure_ascii=False))
        return 2

    directory = ROOT / ('evidence/runtime/zoom-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    before_png, after_png = directory / 'before.png', directory / 'after.png'
    screencap(args.address, args.adb, before_png)
    width, height = 1920, 1080
    if before_png.exists():
        image = cv2.imread(str(before_png))
        if image is not None:
            height, width = image.shape[:2]
    cx, cy = (int(part) for part in args.centre.split(','))
    result = dict(pid=os.getpid(), address=args.address, centre=[cx, cy], radius=args.radius,
                  factor=args.factor, size=[width, height],
                  before=str(before_png.relative_to(ROOT)).replace('\\', '/'),
                  after=str(after_png.relative_to(ROOT)).replace('\\', '/'))
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    try:
        Library.open(Path(args.binary), agent_server=False)
        Toolkit.init_option(prepare())
        device = discover(args.address, args.adb)
        allowed, reason = input_policy(device)
        if not allowed:
            result.update(refused=reason, passed=False)
            Path(ROOT / args.report).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                                encoding='utf-8')
            return 1
        device['input_policy'] = reason
        controller = build(device, input_enabled=True)
        deadline = time.monotonic() + 120
        wait_job(controller.post_connection(), timeout=15, deadline=deadline)
        controller.set_screenshot_target_long_side(1920)
        if args.click:
            x_text, _, y_text = args.click.replace(' ', '').partition(',')
            if x_text.lstrip('-').isdigit() and y_text.lstrip('-').isdigit():
                target = (int(x_text), int(y_text))
                result['click'] = list(target)
                wait_job(controller.post_click(*target), timeout=10, deadline=deadline)
        else:
            result['touches'] = [[pair[0], pair[1]] for pair in
                                 pinch(controller, (cx, cy), args.radius, args.factor)]
        time.sleep(1.0)
        result['passed'] = True
    finally:
        lease.close()
    screencap(args.address, args.adb, after_png)
    Path(ROOT / args.report).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                        encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
