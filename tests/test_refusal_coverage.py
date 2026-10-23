"""Every refusal in the window must carry a reason the recovery table can act on.

This is a ratchet, not a description: adding `_refuse(page, 'a_new_reason')` without
teaching `pages.REFUSALS` about it drops coverage below 100% and fails here.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from maalimbus import pages  # noqa: E402

SOURCE = ROOT / 'src' / 'maalimbus' / 'window.py'
CALL = re.compile(r"_refuse\(\s*[^,]+,\s*'([^']+)'")


def _reasons():
    return [m.group(1) for m in CALL.finditer(SOURCE.read_text(encoding='utf-8'))]


def test_the_scan_actually_sees_refusals():
    reasons = _reasons()
    assert len(reasons) >= 40, f'the scan found only {len(reasons)} refusals'


def test_every_refusal_reason_is_decided():
    undecided = sorted({r for r in _reasons() if r not in pages.REFUSALS})
    assert undecided == [], f'undecided refusal reasons: {undecided[:5]}'


def test_the_tool_reports_full_coverage():
    finished = subprocess.run([sys.executable, str(ROOT / 'tools' / 'refusal_coverage.py')],
                              capture_output=True, text=True)
    assert finished.returncode == 0, finished.stderr
    assert 'coverage 100.0%' in finished.stdout, finished.stdout
