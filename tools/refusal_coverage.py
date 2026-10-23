"""How many refusal sites carry a decided reason, per page.

Reads the real source rather than a remembered number: every `_refuse('<page>', '<reason>')`
literal in `src/maalimbus/window.py`, grouped by page, and whether that reason exists in
`pages.REFUSALS` (so the recovery table can act on it).
"""
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from maalimbus import pages  # noqa: E402

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'maalimbus' / 'window.py'
CALL = re.compile(r"_refuse\(\s*[^,]+,\s*'([^']+)'")

reasons = collections.Counter()
for line in SOURCE.read_text(encoding='utf-8').splitlines():
    found = CALL.search(line)
    if found:
        reasons[found.group(1)] += 1

total = sum(reasons.values())
decided = sum(n for reason, n in reasons.items() if reason in pages.REFUSALS)
silent = [reason for reason in reasons if reason not in pages.REFUSALS]

print(f'sites {total}  decided {decided}  coverage {decided / total:.1%}')
print(f'distinct reasons {len(reasons)}  undecided {len(silent)}')
for reason in sorted(silent)[:8]:
    print('  undecided', reason, reasons[reason])
