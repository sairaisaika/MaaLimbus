"""The audit run against the retained evidence, not against a fixture.

Skipped when no evidence is retained.  It does not assert "the decision table works"
(that needs a live run); it asserts the two things that must hold for *any* retained
evidence, so a regression in the audit itself cannot pass as a green suite.
"""
import glob
import json
import pathlib

import pytest

from maalimbus.evidence_audit import inconsistent_decisions, recovery_kinds, silent_recoveries
from maalimbus.pages import REFUSAL_KINDS, recovery_for

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = sorted(glob.glob(str(ROOT / 'evidence' / 'runtime' / 'packaged-mirror-*')))


def _events():
    events = []
    for directory in EVIDENCE:
        journal = pathlib.Path(directory) / 'events.jsonl'
        if not journal.exists():
            continue
        for line in journal.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    return events


@pytest.fixture(scope='module')
def events():
    if not EVIDENCE:
        pytest.skip('no retained packaged-mirror evidence')
    return _events()


def test_every_recovery_is_either_named_or_counted_as_silent(events):
    report = recovery_kinds(events)
    assert report['named'] + silent_recoveries(report) == report['total']


def test_no_retained_recovery_contradicts_the_kind_table(events):
    # Real evidence may still be silent (nobody named the kind yet); it must never
    # contain a named kind whose action disagrees with the single policy table.
    table = {kind: recovery_for(kind) for kind in REFUSAL_KINDS}
    assert inconsistent_decisions(events, table) == []
