"""How many historical recoveries used to end in `hold`, and how many now reach an action.

`hold` means the engine had a failure in hand and did nothing: no gesture, no re-read, no
escalation.  It is the "stopped without progress" bucket.  This tool replays every
retained run and answers two questions with one number:

* how many named failures existed at all (the denominator),
* how many of them the *literal* tables alone could classify (the old behaviour),
  versus the classifier fallback that shipped in `824b413`.
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))

from maalimbus.pages import REFUSALS, STOP_KINDS, recovery_for  # noqa: E402
from maalimbus.reason_kinds import kind_for  # noqa: E402

NAMED = ('window_recovery', 'mirror_loop_stopped')


def _reason(event):
    for key in ('reason', 'stopped_reason', 'plan_reason'):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def measure(directories):
    total = literal = classified = unresolved = 0
    actions = {}
    leave = {}
    for directory in directories:
        path = os.path.join(directory, 'events.jsonl')
        if not os.path.exists(path):
            continue
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event.get('event') not in NAMED:
                continue
            name = _reason(event)
            if not name:
                continue
            total += 1
            literal_kind = REFUSALS.get(name, STOP_KINDS.get(name))
            if literal_kind:
                literal += 1
            kind = literal_kind or kind_for(name)
            if kind is None:
                unresolved += 1
                leave[name] = leave.get(name, 0) + 1
                continue
            classified += 1
            action = recovery_for(kind)
            actions[action] = actions.get(action, 0) + 1
    return dict(total=total, literal=literal, classified=classified,
                unresolved=unresolved, actions=actions, unresolved_names=leave)


def main():
    directories = sorted(glob.glob(os.path.join(ROOT, 'evidence', 'runtime', 'packaged-mirror-*')))
    result = measure(directories)
    print(f'runs: {len(directories)}')
    print(f'named failures: {result["total"]}')
    print(f'  classified by the literal tables: {result["literal"]}')
    print(f'  classified after the fallback   : {result["classified"]}')
    print(f'  still unclassified (hold)       : {result["unresolved"]}')
    print(f'actions: {dict(sorted(result["actions"].items()))}')
    for name, count in sorted(result['unresolved_names'].items(), key=lambda kv: -kv[1])[:6]:
        print(f'  unresolved x{count}: {name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
