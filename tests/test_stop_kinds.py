from maalimbus.pages import RECOVERY_BY_KIND, REFUSAL_KINDS, STOP_KINDS, kind_of, recovery_for


def test_a_runner_stop_reason_has_a_kind():
    # The live case: evidence/runtime/packaged-mirror-20261023-084610
    assert kind_of(stopped_reason='page_unreadable_after_waiting') == 'unreadable_text'
    assert kind_of(stopped_reason='unexpected_successor') == 'bad_saved_state'


def test_every_stop_kind_is_a_known_kind():
    assert set(STOP_KINDS.values()) <= set(REFUSAL_KINDS)


def test_a_stop_reason_never_shadows_a_refusal_name():
    from maalimbus.pages import REFUSALS
    assert not (set(STOP_KINDS) & set(REFUSALS))


def test_the_three_names_are_tried_in_order():
    assert kind_of(reason='no_candidate_node_observed', stopped_reason='unexpected_successor') == 'no_candidate'
    assert kind_of() is None


def test_the_narrowing_still_reads_one_source():
    # Recording may consult three names; the action table must stay derivable from the kind alone.
    for kind in REFUSAL_KINDS:
        assert recovery_for(kind) == RECOVERY_BY_KIND[kind]


# Measured 2026-10-23: 198 reason-like literals in `src/maalimbus/`, of which only 2 are
# in `REFUSALS`/`STOP_KINDS`.  Counting all 198 made this ratchet answer the wrong
# question: 75 are plan intents and 93 are evidence labels, and no recovery table will
# ever hold them, so a new diagnostic module adding four labels turned the guard red
# without a single unclassified *failure* existing.  The honest denominator is the names
# whose provenance role is failure: 26 of those still have no literal class (measured
# 2026-10-23, down from 187 names counted as "unmapped").
# The prose model (`reason_kinds.role_of`) is the older of the two role models and still
# disagrees with provenance on some names; unifying them is the next architectural step,
# not something this ratchet can decide.
UNMAPPED_FAILURE_BASELINE = 26
# After the role split (intent / outcome / failure) the honest denominator is
# "failures that have no class": 81 on 2026-10-23, down from 187 unmapped names.
UNCLASSIFIED_FAILURE_BASELINE = 81


def test_the_unmapped_reason_vocabulary_only_shrinks():
    import sys
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'tools'))
    from audit_vocabulary import literals
    from maalimbus.pages import REFUSALS, STOP_KINDS
    from maalimbus.reason_provenance import roles

    known = set(REFUSALS) | set(STOP_KINDS)
    decided, _conflicted = roles()
    missing = [name for name in literals()
               if name not in known and decided.get(name) == 'failure']
    assert len(missing) <= UNMAPPED_FAILURE_BASELINE, (
        f'{len(missing)} failure names with no literal class '
        f'(baseline {UNMAPPED_FAILURE_BASELINE}): {sorted(missing)[:5]}')


def test_every_failure_name_has_a_role_and_the_residue_shrinks():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
    from audit_vocabulary import literals
    from maalimbus.pages import REFUSALS, STOP_KINDS
    from maalimbus.reason_kinds import kind_for, role_of

    known = set(REFUSALS) | set(STOP_KINDS)
    names = literals()
    assert all(role_of(name) in ('intent', 'outcome', 'failure') for name in names)
    unclassified = [n for n in names if n not in known
                    and role_of(n) == 'failure' and kind_for(n) is None]
    assert len(unclassified) <= UNCLASSIFIED_FAILURE_BASELINE, (
        f'{len(unclassified)} failure names without a class '
        f'(baseline {UNCLASSIFIED_FAILURE_BASELINE}): {sorted(unclassified)[:5]}')
