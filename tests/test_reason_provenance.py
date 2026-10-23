"""Role comes from where a name is written, not from how it reads."""
from maalimbus.pages import REFUSALS, STOP_KINDS
from maalimbus.reason_kinds import kind_for
from maalimbus.reason_provenance import roles, scan

# Both are real: `provider_error` is an evidence status *and* a failure reason, and the
# shop's save-slot note is recorded as a note and planned as an intent.  Naming them here
# means a *new* conflict fails the test instead of hiding inside a percentage.
KNOWN_CONFLICTS = {
    'provider_error',
    'a_key_saved_slot_is_dead_and_the_shop_sells_the_way_back',
}

# Measured 2026-10-23 by provenance: 128 failure names, 45 of them without a kind.
UNCLASSIFIED_BASELINE = 0


def test_every_reason_name_has_exactly_one_role():
    found = scan()
    _decided, conflicted = roles(found)
    assert found, 'the scan found nothing, which cannot be true of this repository'
    assert set(conflicted) <= KNOWN_CONFLICTS, (
        f'new provenance conflicts: {sorted(set(conflicted) - KNOWN_CONFLICTS)}')


def test_a_failure_name_without_a_kind_only_gets_rarer():
    decided, _conflicted = roles()
    known = set(REFUSALS) | set(STOP_KINDS)
    failures = [name for name, role in decided.items() if role == 'failure']
    assert len(failures) > 80, 'provenance stopped seeing failures, so the count is vacuous'
    without = [name for name in failures if name not in known and kind_for(name) is None]
    assert len(without) <= UNCLASSIFIED_BASELINE, (
        f'{len(without)} failure names without a kind (baseline {UNCLASSIFIED_BASELINE}): '
        f'{sorted(without)[:5]}')
