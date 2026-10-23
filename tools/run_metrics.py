"""Print the phase-6 table for the stored runs: python tools/run_metrics.py [runs]"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from maalimbus.run_metrics import summarise          # noqa: E402

EVIDENCE = ROOT / 'evidence' / 'runtime'


def load(run):
    path = run / 'events.jsonl'
    if not path.exists():
        return None
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def main(argv):
    limit = int(argv[1]) if len(argv) > 1 else 8
    runs = sorted((p for p in EVIDENCE.glob('packaged-mirror-*') if (p / 'events.jsonl').exists()),
                  key=lambda p: (p / 'events.jsonl').stat().st_mtime)[-limit:]
    if not runs:
        print('no stored runs')
        return 1
    for run in runs:
        rows = load(run)
        if not rows:
            continue
        s = summarise(rows)
        rate = 'n/a' if s['recovery_rate'] is None else f"{s['recovery_rate']:.2f}"
        e = s['recovery_effect']
        eff = 'n/a' if e['rate'] is None else f"{e['effective']}/{e['recoveries']}"
        a = s['recovery_advanced']
        adv = 'n/a' if a['rate'] is None else f"{a['advanced']}/{a['recoveries']}"
        print(f"{run.name}  events={s['events']:<4} frames={s['frames']:<3} "
              f"floors={s['floors']} verdicts={s['verdicts']} "
              f"recovery_rate={rate} busy={eff} advanced={adv} "
              f"stops={s['stop_reasons']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
