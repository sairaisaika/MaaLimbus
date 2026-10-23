"""How many reason-like names exist, and how many of them the kind table knows.

Measured 2026-10-23: 189 distinct literals across `src/maalimbus/`, of which only 2
were in `REFUSALS`/`STOP_KINDS`.  That ratio is the architecture defect, made
countable so it can only shrink.
"""
import ast
import glob
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.pages import REFUSALS, STOP_KINDS  # noqa: E402
from maalimbus.reason_kinds import kind_for, role_of  # noqa: E402

KEYS = ('reason', 'stopped', 'stopped_reason', 'plan_reason')


def literals(source_dir=None):
    found = set()
    for name in glob.glob(str(source_dir or ROOT / 'src' / 'maalimbus' / '*.py')):
        tree = ast.parse(pathlib.Path(name).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (isinstance(key, ast.Constant) and key.value in KEYS
                            and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                        found.add(value.value)
            elif isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if (keyword.arg in KEYS and isinstance(keyword.value, ast.Constant)
                            and isinstance(keyword.value.value, str)):
                        found.add(keyword.value.value)
                if (isinstance(node.func, ast.Attribute) and node.func.attr == '_refuse'
                        and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                        and isinstance(node.args[1].value, str)):
                    found.add(node.args[1].value)
    return found


def main():
    known = set(REFUSALS) | set(STOP_KINDS)
    names = literals()
    missing = sorted(name for name in names if name not in known)
    roles = {name: role_of(name) for name in names}
    failures = [name for name in names if name not in known and roles[name] == 'failure']
    unclassified = [name for name in failures if kind_for(name) is None]
    # The recovery table can only answer for names that are failures; plan intents and
    # evidence labels never get a class, so counting them as "unmapped" measures the size
    # of the prose vocabulary instead of the debt the table owes.
    from maalimbus.reason_provenance import roles as provenance_roles
    decided, conflicted = provenance_roles()
    owed = sorted(name for name in names
                  if name not in known and decided.get(name) == 'failure')
    owed_unclassified = [name for name in owed if kind_for(name) is None]
    prose_failures = set(failures)
    disagree = len(prose_failures ^ set(owed))
    print(f'reason-like literals: {len(names)}')
    print(f'prose role model (reason_kinds): intents '
          f'{sum(1 for r in roles.values() if r == "intent")}'
          f'  outcomes {sum(1 for r in roles.values() if r == "outcome")}'
          f'  failures {sum(1 for r in roles.values() if r == "failure")}')
    print(f'mapped: {len(names) - len(missing)}  unmapped literals: {len(missing)}'
          f'  of which provenance calls failures: {len(owed)}')
    print(f'failures without a class: provenance {len(owed_unclassified)}'
          f'  prose model {len(unclassified)}'
          f'  (the two role models disagree on {disagree} unmapped names)')
    print(f'provenance conflicts: {len(conflicted)}')
    missing = owed_unclassified or unclassified or owed or missing
    for name in missing[:10]:
        print(f'  - {name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
