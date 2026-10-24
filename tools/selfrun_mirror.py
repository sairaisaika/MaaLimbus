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

# The loop's own budget is checked between steps, so its overshoot is one step long.
# Measured across the retained attempts: 12.3, 12.3, 13.3 and 15.2 s.  The harness waits
# this much past the budget so a healthy run can end itself and write its ending; a kill
# that happens anyway is written into the run's own directory (D78) instead of leaving the
# run to be counted as a death.
MARGIN_SECONDS = 45


# A killed verifier does not kill the agent it started: `subprocess.run(timeout=...)`
# kills the direct child only, and on Windows no signal travels down.  The 2026-10-24
# 04:59 attempt left `MaaLimbusAgent.exe` holding the controller lease, so the next
# attempt wrote no event at all for 481 s and looked like a silent death (D94).
AGENT_IMAGE = 'MaaLimbusAgent.exe'
REAP_SECONDS = 20.0


def _tasklist():
    out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True,
                         text=True, timeout=REAP_SECONDS).stdout or ''
    rows = []
    for line in out.splitlines():
        parts = [cell.strip('"') for cell in line.strip().split('","')]
        if len(parts) >= 2 and parts[1].isdigit():
            rows.append((int(parts[1]), parts[0].strip('"')))
    return rows


def _taskkill(pid):
    """`/T` is the point: the agent is a child of the verifier, and killing the parent
    alone leaves it running with the controller lease (measured 2026-10-24)."""
    done = subprocess.run(['taskkill', '/F', '/T', '/PID', str(int(pid))],
                          capture_output=True, text=True, timeout=REAP_SECONDS)
    return done.returncode == 0


def agent_processes(list_processes=None):
    """Pids of the packaged agent image that are still running."""
    lister = _tasklist if list_processes is None else list_processes
    return [pid for pid, image in lister() if image.lower() == AGENT_IMAGE.lower()]


def reap(pid, kill=None):
    """Kill a process and every child it started; True when the kill was issued."""
    killer = _taskkill if kill is None else kill
    return bool(killer(pid))


def reap_stale_agents(*, list_processes=None, kill=None):
    """Kill agents a previous attempt left behind, and say how many were found."""
    pids = agent_processes(list_processes)
    killed = [pid for pid in pids if reap(pid, kill)]
    return {'found': pids, 'killed': killed}


def run_bounded(command, *, cwd, timeout, kill=None, reap_seconds=REAP_SECONDS):
    """Run a command; on overrun kill the whole tree and still hand back its output."""
    process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        out, err = process.communicate(timeout=timeout)
        return {'returncode': process.returncode, 'stdout': out or '', 'stderr': err or '',
                'killed': False, 'reaped': None}
    except subprocess.TimeoutExpired:
        reaped = reap(process.pid, kill)
        try:
            out, err = process.communicate(timeout=reap_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            out, err = '', ''
        return {'returncode': 124, 'stdout': out or '', 'stderr': err or '',
                'killed': True, 'reaped': reaped}


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
    # A previous attempt that was killed can still own the controller: the 2026-10-24
    # 04:59 attempt left an agent behind and the next one wrote no event for 481 s.
    record['stale_agents'] = reap_stale_agents()
    # The budget is still enforced from outside, because a caller cannot take its own
    # wall clock away.  On overrun the whole process tree is killed (D94), and the kill
    # is recorded in the run's own directory (D78) so it cannot read as a death.
    finished = run_bounded([sys.executable, str(ROOT / 'tools/verify_packaged_mirror_loop.py'),
                            '--app', str(ROOT / 'dist' / 'MaaLimbus'),
                            '--address', '127.0.0.1:16416',
                            '--adb', ADB,
                            '--authorize', nonce,
                            '--steps', '400', '--seconds', str(seconds)],
                           cwd=str(ROOT), timeout=seconds + MARGIN_SECONDS)
    killed_by_budget = bool(finished['killed'])
    record['reaped'] = finished.get('reaped')
    record['exit'] = finished['returncode']
    record['elapsed_s'] = round(time.time() - started, 1)
    # A driver-level silent death: the verifier can refuse in under a second (gate,
    # stale freeze, missing address) and this record used to say only `exit: 1`.
    if finished['returncode'] != 0:
        tail = (finished['stderr'] or finished['stdout'] or '').strip().splitlines()
        # Twelve lines, not one: a traceback's last line names the exception and its
        # first lines name the frame that raised it -- the only way to tell a click
        # apart from a deadline without another live run.
        record['error_tail'] = ' | '.join(tail[-12:])[:1500] if tail else 'no_output'
        # The verifier answers a refusal with a JSON object that names the reason;
        # lift it so the record says "refused: <why>" instead of a JSON prefix.
        try:
            body = json.loads(finished['stdout'] or '')
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
    if killed_by_budget:
        record['stop'] = 'the_budget_ended_the_run'
        record['note'] = 'the harness killed the run at its budget; the loop did not stop itself'
        # The killed process cannot write its ending, so the process that killed it does.
        # `run_metrics.ending` reads this file and reports the run as `budget` instead of
        # `died`; without it the census counts a healthy run as a death (D78).
        (directory / 'harness.json').write_text(json.dumps({
            'killed_by_budget': True,
            'stop': record['stop'],
            'seconds': seconds,
            'margin_seconds': MARGIN_SECONDS,
            'elapsed_s': record['elapsed_s'],
            'exit': record['exit'],
            'utc': record['utc'],
        }, ensure_ascii=False) + '\n', encoding='utf-8')
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
