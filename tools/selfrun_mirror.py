"""Run the packaged Mirror Dungeon loop repeatedly and score attempts by one thing only.

The condition this optimises is the player's own: **reach floor 5**. Everything else a
run does -- which page it thought it saw, which node it clicked, where it stopped -- is
recorded per attempt and scored later, so a reading bug becomes one failed attempt out
of many instead of a session that has to be nursed frame by frame.

Each attempt is the existing driver run unchanged; this only decides whether to start
another one, and keeps a durable record of how each attempt ended. It does not restart
the game itself: until the end-of-run circle is proven, an attempt that ends anywhere
but the map stops the series, and that stop is the evidence of what the circle still
needs.

    python tools/selfrun_mirror.py --attempts 200
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))
from maalimbus import crash_codes  # noqa: E402  (after the path is in place)
LOG = ROOT / 'build' / 'selfrun-mirror.jsonl'
ADB = r'D:\\Program Files\\Netease\\MuMu\\nx_main\\adb.exe'


def attempt(index: int, seconds: int) -> dict:
    record = {'attempt': index, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'seconds': seconds}
    started = time.time()
    # The verifier grew required --app/--address (and a real nonce) after this driver
    # was written; it was failing in 0.4 s with exit 2 and re-reading the previous
    # run's evidence directory, which looks like "the run did nothing".
    nonce = __import__('uuid').uuid4().hex
    (ROOT / 'build' / 'map-probe-authorization.json').write_text(
        json.dumps({'live_input_authorized': True, 'nonce': nonce}), encoding='utf-8')
    finished = subprocess.run([sys.executable, str(ROOT / 'tools/verify_packaged_mirror_loop.py'),
                               '--app', str(ROOT / 'dist' / 'MaaLimbus'),
                               '--address', '127.0.0.1:16416',
                               '--adb', ADB,
                               '--authorize', nonce,
                               '--steps', '400', '--seconds', str(seconds)],
                              cwd=str(ROOT), capture_output=True, text=True)
    record['exit'] = finished.returncode
    record['elapsed_s'] = round(time.time() - started, 1)
    reports = sorted((ROOT / 'evidence/runtime').glob('packaged-mirror-*'),
                     key=lambda p: p.stat().st_mtime)
    if not reports:
        record['outcome'] = 'no_evidence_directory'
        return record
    directory = reports[-1]
    record['evidence'] = str(directory.relative_to(ROOT))
    events = []
    path = directory / 'events.jsonl'
    if path.exists():
        events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
                  if line.strip()]
    record['events'] = len(events)
    record['floors'] = sorted({e['floor'] for e in events
                               if e['event'] == 'map_observed' and e.get('floor')})
    stops = [e.get('reason') for e in events if e['event'] in ('mirror_loop_stopped', 'mirror_loop_error')]
    # A native death leaves no stop event, so the exit code is the only cause
    # left.  Without this the run counts as "ended without a stop" and its
    # cause vanishes (`src/maalimbus/crash_codes.py`).
    record['stop'] = (stops[0] if stops
                      else crash_codes.name_for(exit_code))
    record['reached_floor_5'] = 5 in record['floors']
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempts', type=int, default=200)
    parser.add_argument('--seconds', type=int, default=1800,
                        help='wall clock per attempt before the driver gives up')
    args = parser.parse_args()
    consecutive_unproductive = 0
    for index in range(1, args.attempts + 1):
        record = attempt(index, args.seconds)
        with LOG.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(json.dumps(record, ensure_ascii=False))
        if record['reached_floor_5']:
            print('reached floor 5 on attempt %d' % index)
            return 0
        # Two attempts in a row that never reach the dungeon mean the series is not
        # measuring runs any more; stop rather than burn the budget on a stuck client.
        consecutive_unproductive = consecutive_unproductive + 1 if not record['floors'] else 0
        if consecutive_unproductive >= 2:
            print('two attempts in a row never reached a dungeon floor; stopping')
            return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
