"""Read the retained evidence and report whether the recovery engine decided anything.

    python tools/audit_evidence.py            # every evidence/runtime/packaged-mirror-*
    python tools/audit_evidence.py DIR ...    # specific run directories

Exit codes: 0 = every recovery named its decision and matched the table;
1 = at least one silent recovery or one inconsistent action; 2 = no evidence found
(an empty scan is a failure, never a pass).
"""
import glob
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.evidence_audit import derivable_kinds, frozen_build, inconsistent_decisions, recovery_kinds, silent_recoveries


def load(directory):
    events = []
    journal = pathlib.Path(directory) / 'events.jsonl'
    if not journal.exists():
        return events
    for line in journal.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def main(argv):
    directories = argv[1:] or sorted(glob.glob(str(
        ROOT / 'evidence' / 'runtime' / 'packaged-mirror-*')))
    if not directories:
        print('no evidence directories found')
        return 2
    events = []
    for directory in directories:
        events.extend(load(directory))
    report = recovery_kinds(events)
    wrong = inconsistent_decisions(events)
    build = frozen_build()
    print(f'frozen build: {build["commit"][:8]}  dirty {build["dirty"]}')
    print(f'directories: {len(directories)}')
    print(f"window_recovery: {report['total']}  named: {report['named']}  "
          f"silent: {silent_recoveries(report)}")
    print(f"kinds: {report['kinds']}")
    derived = derivable_kinds(events)
    print(f"derived (analysis, not recorded): {derived['derived']} {derived['kinds']}")
    print(f"actions: {report['actions']}")
    print(f"covers_the_decision_table: {report['covers_the_decision_table']}")
    print(f'inconsistent decisions: {len(wrong)}')
    for item in wrong[:5]:
        print(f"  {item['page']}: kind={item['kind']} recorded={item['recorded']} "
              f"expected={item['expected']}")
    if not report['total']:
        print('RESULT: no recoveries at all — nothing is proven')
        return 2
    if not report['covers_the_decision_table'] or wrong:
        print('RESULT: the decision table did not drive every recovery')
        return 1
    print('RESULT: every recovery named a kind and spent that kind\'s action')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
