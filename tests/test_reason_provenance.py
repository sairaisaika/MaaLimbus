"""Role comes from where a name is written, not from how it reads."""
import ast

import maalimbus.reason_provenance as provenance
from maalimbus.pages import REFUSALS, STOP_KINDS
from maalimbus.reason_kinds import kind_for
from maalimbus.reason_provenance import _Walk, roles, scan

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


def _role_in(source):
    walker = _Walk('snippet.py')
    walker.visit(ast.parse(source))
    return {name: {role for role, _site in sites} for name, sites in walker.found.items()}


# Measured 2026-10-23: these seven names were the whole "failure without a kind" residue,
# and every one of them was a label inside a record that had already decided itself:
# `click_trace.classify` returns {'kind', 'action', 'reason'}, `jobs.controller_ready`
# returns {'ready', 'reason'}, `runner.wait_decision` returns {'stop', 'reason'}.  The
# prose inferer read all seven as failures -- including `the_controller_id_is_present`,
# which is a *success*.  A record that names its own class does not need its prose read.
def test_a_record_that_names_its_own_class_needs_no_kind():
    roles_of = _role_in('''
def classify(*, seconds_since_click):
    if seconds_since_click < 5:
        return {'kind': 'within_the_trace_window', 'action': 'keep_waiting',
                'reason': 'the_click_had_not_had_time_to_show_an_effect'}
    return {'ready': True, 'reason': 'the_controller_id_is_present'}
''')
    assert roles_of['the_click_had_not_had_time_to_show_an_effect'] == {'evidence'}
    assert roles_of['the_controller_id_is_present'] == {'evidence'}


def test_a_decision_in_prose_alone_is_still_a_failure():
    # The counter-example: the exemption above must not swallow a complaint.  A record
    # with a reason and no decided key of its own still owes the table a class.
    roles_of = _role_in('''
def verdict():
    return {'reason': 'the_screen_never_answered', 'step': 3}
''')
    assert roles_of['the_screen_never_answered'] == {'failure'}


def test_a_refused_name_is_a_failure_wherever_it_is_also_a_label():
    # Exemption is per *record*, not per name: the same name at a `_refuse` call site is
    # still a refusal, and provenance keeps both facts so `roles()` can call it a conflict
    # instead of letting one site quietly win.
    roles_of = _role_in('''
def step(result):
    verdict = {'passed': False, 'reason': 'the_page_never_moved'}
    if verdict:
        _refuse(result, 'the_page_never_moved', None)
''')
    assert roles_of['the_page_never_moved'] == {'failure', 'evidence'}


def test_the_exemption_is_not_switched_on_for_a_bare_boolean_flag():
    # `stop: False` decides "do not stop"; it is still a decision, so its reason is a
    # label.  Only a record with no decided key at all keeps the failure role.
    roles_of = _role_in('''
def decide(waited):
    return {'note': waited % 5 == 0, 'stop': False,
            'reason': 'a_waiting_step_is_still_a_step'}
''')
    assert roles_of['a_waiting_step_is_still_a_step'] == {'evidence'}
    assert provenance.DECIDED_KEYS == ('kind', 'verdict')


def test_a_plan_table_is_a_plan_wherever_it_is_written():
    # D47 moved 27 single-shape branches out of `_plan_step` into the module-level
    # `window.STEP_ROWS`.  The reasons did not change meaning, but the old rule keyed on
    # the enclosing function's name, so every one of them started reading as a failure.
    # A mapping that names the control it uses and the pages it expects *is* a plan.
    roles_of = _role_in('''
STEP_ROWS = {
    'HOME': {'control': 'home.drive_button', 'expect': ('DRIVE',),
             'reason': 'drive_nav_is_the_proven_way_back', 'refusal': 'not_anchored'},
}
''')
    assert roles_of['drive_nav_is_the_proven_way_back'] == {'intent'}


def test_a_record_that_only_mentions_a_reason_is_still_a_failure_in_a_table():
    # The plan exemption must not swallow a diagnostic that happens to sit in a mapping
    # next to other data: none of PLAN_KEYS is present, so nothing decided this one.
    roles_of = _role_in('''
NOTES = {'HOME': {'reason': 'the_header_never_came_back', 'page': 'HOME'}}
''')
    assert roles_of['the_header_never_came_back'] == {'failure'}
    assert provenance.PLAN_KEYS == ('control', 'expect', 'refusal')
