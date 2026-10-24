"""Price every screencap method this device offers, without sending input.

D66 gave a read 2.45 s from the journal's gaps and D68 measured the node itself at
1.08-1.44 s through replay, so roughly a second per read is device capture. Which
method that capture uses is Maa's choice: `adb_device.build` hands the discovered
bitmask over and the framework picks. `pin_input` exists for the input half and there
was no `pin_screencap` for this half, so the capture cost could be measured only by
guessing.

This tool does the measuring: for each method the binding offers it builds a
controller with that one bit and the Null input method, times N captures, and prints
the table. Nothing here clicks, swipes or presses a key: `input_policy` reports the
binding and the controller is built with `input_enabled=False`, which is the same
guarantee `tools/map_live_observe.py` gives.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maa.define import MaaAdbInputMethodEnum
from maa.library import Library

from maalimbus.adb_device import SCREENCAP_NAMES, discover, input_policy, names
from maalimbus.jobs import ScreenshotNeverReturned, screencap
from maa.controller import AdbController


def price(record, bit, *, count, timeout):
    """Time `count` captures through one method bit; returns the seconds list."""
    controller = AdbController(record['adb_path'], record['address'], bit,
                               int(MaaAdbInputMethodEnum.Null), record['config'])
    seconds = []
    try:
        from maalimbus.jobs import wait_job
        wait_job(controller.post_connection(), timeout=15)
        for _ in range(count):
            started = time.monotonic()
            try:
                screencap(controller, timeout=timeout)
            except ScreenshotNeverReturned:
                seconds.append(None)
                continue
            seconds.append(round(time.monotonic() - started, 3))
    finally:
        try:
            controller.post_disconnect()
        except AttributeError:
            pass
    return seconds


def survey(record, *, count=5, timeout=10.0, clock=time.monotonic):
    """Price every offered method; a method that fails is reported, not dropped."""
    rows = []
    for bit, name in sorted(SCREENCAP_NAMES.items()):
        if not int(record.get('screencap_methods', 0)) & bit:
            continue
        seconds = price(record, bit, count=count, timeout=timeout)
        good = [value for value in seconds if value is not None]
        rows.append({'method': name, 'bit': bit, 'count': count,
                     'failures': len(seconds) - len(good),
                     'mean': round(statistics.fmean(good), 3) if good else None,
                     'median': round(statistics.median(good), 3) if good else None})
    return rows


def fastest(rows):
    """The method with the lowest median, or None when nothing was measured."""
    measured = [row for row in rows if row['median'] is not None]
    if not measured:
        return None
    return min(measured, key=lambda row: row['median'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--binary', default=str(ROOT / 'build/mxu-probe-271/maafw'))
    parser.add_argument('--adb', default=None)
    parser.add_argument('--address', default='127.0.0.1:16416')
    parser.add_argument('--count', type=int, default=5)
    parser.add_argument('--timeout', type=float, default=10.0)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--directory', default=None)
    args = parser.parse_args(argv)

    Library.open(Path(args.binary), agent_server=False)
    record = discover(args.address, args.adb)
    allowed, reason = input_policy(record, allow_fallback=False)
    rows = survey(record, count=args.count, timeout=args.timeout)
    best = fastest(rows)
    report = {'address': args.address, 'input_sent': False,
              'input_policy': {'allowed': allowed, 'reason': reason},
              'offered': names(int(record.get('screencap_methods', 0)), SCREENCAP_NAMES),
              'captures_per_method': args.count,
              'methods': rows,
              'fastest': None if best is None else best['method'],
              'fastest_median': None if best is None else best['median'],
              'slowest_median': max((row['median'] for row in rows
                                     if row['median'] is not None), default=None),
              'captured_at': datetime.now().isoformat(timespec='seconds')}
    if args.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    else:
        print('device:', report['address'], ' input sent:', report['input_sent'])
        print('offered screencap methods:', report['offered'])
        for row in rows:
            if row['median'] is None:
                print(f"  {row['method']:<22} never returned ({row['failures']} of {row['count']})")
            else:
                print(f"  {row['method']:<22} median {row['median']:.3f} s  "
                      f"mean {row['mean']:.3f} s  ({row['failures']} failed)")
        if best is not None:
            print(f"fastest: {best['method']} at {best['median']:.3f} s per capture")
        else:
            print('no method returned a frame: nothing was measured, which is not 0 s')
    if args.directory:
        directory = Path(args.directory)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'screencap.json').write_text(
            json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
        print('wrote', directory / 'screencap.json')
    return 0 if best is not None else 1


if __name__ == '__main__':
    raise SystemExit(main())
