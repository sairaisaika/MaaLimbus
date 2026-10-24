"""A mode switch that changed no page may not be sent again (D111).

Live `evidence/runtime/packaged-mirror-20261024-092229` sent twenty toggles for nine
submitted turns: after an assignment the dial is often not found, and the plan answered
the missing dial with the same mode switch instead of naming it.
"""
from maalimbus import pages, window

SIZE = (1920, 1080)
TOGGLES = {'win_rate': [1590, 794, 120, 44], 'damage': [1590, 856, 120, 44]}
DIAL = [1340, 795, 77, 78]


def _plan(box=DIAL, assigns=0, previous='assign', auto=None):
    return window.plan_step('BATTLE_HUD', start_box=box, auto_assign=auto or TOGGLES,
                            battle_previous=previous, battle_assigns=assigns)


def test_the_dial_is_submitted_when_it_is_there():
    plan = _plan()
    assert plan['review_reason'] if 'review_reason' in plan else True
    assert plan['reason'] == 'start_button_submits_the_assigned_turn'
    assert plan['target'] == DIAL


def test_a_missing_dial_is_answered_with_the_mode_while_the_budget_lasts():
    first = _plan(box=None, assigns=0)
    assert first['reason'] == 'win_rate_is_the_proven_auto_assign_control'
    assert first['target'] == TOGGLES['win_rate']
    for assigns in (1, 3):
        again = _plan(box=None, assigns=assigns)
        assert again['reason'] == 'win_rate_is_the_proven_auto_assign_control'
    assert window.MAX_BATTLE_ASSIGNS == 4


def test_after_the_budget_the_missing_dial_is_named_not_re_clicked():
    plan = _plan(box=None, assigns=window.MAX_BATTLE_ASSIGNS)
    assert plan['reason'] == 'the_submit_dial_was_not_found_after_the_assignment'
    assert plan['action'] == window.RECORD
    assert plan['target'] is None


def test_the_named_missing_dial_is_a_missing_control():
    assert pages.REFUSALS['the_submit_dial_was_not_found_after_the_assignment'] == 'missing_control'
    assert pages.recovery_for(
        pages.REFUSALS['the_submit_dial_was_not_found_after_the_assignment']
    ) in pages.WAIT_ONLY_ACTIONS


def test_the_submit_still_resets_the_budget_from_the_runner_side():
    source = __import__('pathlib').Path('src/maalimbus/runner.py').read_text(encoding='utf-8')
    assert "state['battle_assigns']=int(state.get('battle_assigns') or 0)+1" in source
    assert "state['battle_assigns']=0" in source
