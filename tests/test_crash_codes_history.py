"""Every native death the harness has ever recorded is nameable.

Measured on `build/selfrun-mirror.jsonl` (61 runs): 7 carried ``stop: null``
with exit ``3221226505``.  They entered the metrics as "ended without a stop",
i.e. the same bucket as an operator kill.  This test keeps that mapping
complete for whatever codes the local corpus actually contains.
"""

import json
from pathlib import Path

import pytest

from maalimbus import crash_codes

LOG = Path(__file__).resolve().parent.parent / 'build' / 'selfrun-mirror.jsonl'


@pytest.mark.skipif(not LOG.exists(), reason='no harness log on this machine')
def test_no_recorded_crash_is_left_unnamed():
    unnamed = []
    for line in LOG.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        code, stop = row.get('exit'), row.get('stop')
        # 0/1 are ordinary harness exits; 2 is the verifier refusing to start on a
        # bad argument (guarded by its own tests), not a native death.
        if stop is not None or code in (None, 0, 1, 2):
            continue
        if crash_codes.name_for(code) is None:
            unnamed.append(code)
    assert not unnamed, f'native exit codes with no name: {sorted(set(unnamed))}'
