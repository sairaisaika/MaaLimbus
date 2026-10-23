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
from maalimbus import run_record  # noqa: E402  (after the path is in place)
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
    # A driver-level silent death: the verifier can refuse in under a second (gate,
    # stale freeze, missing address) and this record used to say only `exit: 1`.
    if finished.returncode != 0:
        tail = (finished.stderr or finished.stdout or '').strip().splitlines()
        # Twelve lines, not one: a traceback's last line names the exception and its
        # first lines name the frame that raised it -- the only way to tell a click
        # apart from a deadline without another live run.
        record['error_tail'] = ' | '.join(tail[-12:])[:1500] if tail else 'no_output'
        # The verifier answers a refusal with a JSON object that names the reason;
        # lift it so the record says "refused: <why>" instead of a JSON prefix.
        try:
            body = json.loads(finished.stdout or '')
        except ValueError:
            body = {}
        if isinstance(body, dict) and body.get('refused'):
            record['refused'] = body['refused']
        if isinstance(body, dict) and body.get('hint'):
            record['hint'] = body['hint']
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
    record.update(run_record.summarise(events, record['exit']))
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
