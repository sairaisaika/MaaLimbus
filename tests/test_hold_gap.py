"""The corpus is the only honest measure of how often the engine did nothing."""
import glob
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from audit_hold_gap import measure  # noqa: E402

CORPUS = sorted(glob.glob(os.path.join(ROOT, 'evidence', 'runtime', 'packaged-mirror-*')))

# Measured 2026-10-23 over 124 runs: 266 named failures, 223 classified, 43 still hold.
HOLD_BASELINE = 0


@pytest.mark.skipif(not CORPUS, reason='no retained runs in this checkout')
def test_the_number_of_failures_that_still_hold_only_falls():
    result = measure(CORPUS)
    assert result['total'] > 100, 'the corpus shrank, so the number would be vacuous'
    assert result['classified'] >= result['literal'], 'the fallback lost ground'
    assert result['unresolved'] <= HOLD_BASELINE, (
        f'{result["unresolved"]} failures still hold (baseline {HOLD_BASELINE}): '
        f'{sorted(result["unresolved_names"])[:5]}')
