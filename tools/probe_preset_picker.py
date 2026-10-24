"""One authorised click on the pre-battle preset plate, with before/after evidence.

The pre-battle page prints `Preset #1` on a small plate with a shuffle glyph beside it,
and the ledger's rotation lists another team.  Pressing the *text* did nothing (four
presses, live `…-114050`), so the glyph is the other candidate control.  This probe reads
the page, clicks one point, reads again and saves both frames: it is a measurement, not a
fix, and it sends exactly one click.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'agent'))

import cv2
from maa.library import Library
from maa.toolkit import Toolkit

from maalimbus.adb_device import build, discover, foreground_of
from maalimbus.controller_lease import ControllerLease, lease_path
from maalimbus.jobs import wait_job


def _capture(controller, directory, name, deadline):
    """One frame on disk: the evidence this probe is for."""
    wait_job(controller.post_screencap(), timeout=15, deadline=deadline)
    image = controller.cached_image
    if image is None:
        raise RuntimeError('the controller returned no frame')
    cv2.imwrite(str(directory / (name + '.png')), image)
    return image


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--binary', default=str(ROOT / 'build/mxu-probe-271/maafw'))
    ap.add_argument('--address', default='127.0.0.1:16416')
    ap.add_argument('--point', default='258,276', help='x,y of the click')
    ap.add_argument('--directory', default=None)
    args = ap.parse_args(argv)
    directory = Path(args.directory or (ROOT / 'evidence/runtime' /
                     ('preset-probe-' + datetime.now().strftime('%Y%m%d-%H%M%S'))))
    directory.mkdir(parents=True, exist_ok=True)
    Library.open(Path(args.binary))
    Toolkit.init_option(Path(args.binary))
    device = discover(args.address)
    if device is None:
        raise SystemExit('no device at ' + args.address)
    lease = ControllerLease.acquire(ROOT / 'controller.lock')
    try:
        controller = build(device, input_enabled=True)
        controller.post_connection().wait()
        app = foreground_of(device)
        deadline = time.monotonic() + 60
        record = {'run': directory.name, 'foreground_before': app,
                  'input_sent': False, 'clicked': None}
        if 'Limbus' not in (app or ''):
            record['reason'] = 'foreground_is_not_limbus'
        else:
            before = _capture(controller, directory, 'before', deadline)
            x, y = (int(value) for value in args.point.split(','))
            controller.post_click(x, y).wait()
            time.sleep(1.8)
            record['input_sent'] = True
            record['clicked'] = [x, y]
            after = _capture(controller, directory, 'after', deadline)
            difference = float(cv2.absdiff(before, after).mean())
            record['frame_difference'] = round(difference, 2)
            record['changed'] = difference > 2.0
        (directory / 'result.json').write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
        print(json.dumps(record, ensure_ascii=False))
        print('directory:', directory)
    finally:
        lease.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
