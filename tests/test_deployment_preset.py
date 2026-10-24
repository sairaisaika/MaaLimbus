"""A board showing another saved team may not be deployed.

`evidence/runtime/packaged-mirror-20261024-111024`: the page printed 'Preset #1' while
the ledger's team was 2, and the loop cleared the inherited participant order on the
board's team anyway -- an input the transaction could never verify, four waits, then a
stop. Nothing on that page can be proven against the ledger, so the page is refused by
name and the loop never acts on the wrong team (D117).
"""
import maalimbus.window as window
from maalimbus import pages


def _controls():
    return {'pre_battle.clear_selection': (1651, 669, 173, 97),
            'pre_battle.battle': (1651, 832, 192, 97)}


def test_a_preset_mismatch_refuses_the_page_before_any_deployment_action():
    plan = window.plan_step('PRE_BATTLE_TEAM', controls=_controls(),
                            team={'preset_mismatch': True, 'reset_required': True,
                                  'states': [], 'participants': [], 'order': []})
    assert plan['action'] == 'record'
    assert plan['reason'] == ('the_board_shows_a_different_saved_team_than_the_plan_deploys')
    assert plan['target'] is None


def test_without_the_mismatch_the_reset_still_clears_the_inherited_order():
    plan = window.plan_step('PRE_BATTLE_TEAM', controls=_controls(),
                            team={'reset_required': True, 'states': [], 'participants': [],
                                  'order': []})
    assert plan['action'] == 'click'
    assert plan['reason'] == ('clear_inherited_participant_order_before_saved_deployment')


def test_the_refusal_is_a_state_failure_and_never_deploys_the_wrong_team():
    kind = pages.REFUSALS['the_board_shows_a_different_saved_team_than_the_plan_deploys']
    assert kind == 'bad_saved_state'
    assert pages.recovery_for(kind) == 'escalate_ladder'
    # The ladder is a viewport gesture list (D62): it cannot deploy, assign or submit, so
    # "escalate" is safe on this page while "act on the board" is not.
    rungs = pages.ladder_for('escalate_ladder', ('pinch_out', 'drag_up', 'wait'))
    assert rungs == ('pinch_out', 'drag_up', 'wait')
    assert pages.recovery_for(kind) != 'stop'
