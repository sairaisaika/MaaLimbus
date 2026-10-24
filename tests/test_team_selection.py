"""A page showing another saved team is asked to show the right one, four times.

D117 refused the page by name, and its first live effect was a stop at 14 s with zero
clicks (`packaged-mirror-20261024-113756`): the safe answer was also a dead end.  The
header that prints `Preset #1` is the control that opens the preset column, so the plan
presses it and reads again -- bounded, because a column that has not cycled in
SELECT_TEAM_TRIES presses is not going to.
"""
import maalimbus.window as window
from maalimbus import pages, team_vision


def _controls():
    return {'pre_battle.clear_selection': (1651, 669, 173, 97),
            'pre_battle.battle': (1651, 832, 192, 97)}


def _team(**extra):
    team = {'preset_mismatch': True, 'states': [], 'participants': [], 'order': [],
            'saved_team': 1, 'saved_team_box': [150, 254, 84, 21], 'tries': 0}
    team.update(extra)
    return team


def test_a_mismatch_presses_the_header_it_read():
    plan = window.plan_step('PRE_BATTLE_TEAM', controls=_controls(), team=_team())
    assert plan['action'] == 'click'
    assert plan['reason'] == 'the_saved_team_is_selected_on_the_board'
    assert plan['target'] == [150, 254, 84, 21] or tuple(plan['target']) == (150, 254, 84, 21)


def test_the_column_gets_a_bounded_number_of_presses():
    plan = window.plan_step('PRE_BATTLE_TEAM', controls=_controls(),
                            team=_team(tries=pages.SELECT_TEAM_TRIES - 1))
    assert plan['reason'] == 'the_saved_team_is_selected_on_the_board'
    plan = window.plan_step('PRE_BATTLE_TEAM', controls=_controls(),
                            team=_team(tries=pages.SELECT_TEAM_TRIES))
    assert plan['action'] == 'record'
    assert plan['reason'] == 'the_board_shows_a_different_saved_team_than_the_plan_deploys'


def test_a_header_with_no_box_is_still_refused():
    plan = window.plan_step('PRE_BATTLE_TEAM', controls=_controls(),
                            team=_team(saved_team_box=None))
    assert plan['action'] == 'record'
    assert plan['reason'] == 'the_board_shows_a_different_saved_team_than_the_plan_deploys'


def test_the_refusal_is_what_the_ladder_and_the_census_see():
    kind = pages.REFUSALS['the_board_shows_a_different_saved_team_than_the_plan_deploys']
    assert kind == 'bad_saved_state'
    assert pages.recovery_for(kind) == 'escalate_ladder'


def test_the_reader_hands_over_the_header_box():
    from maalimbus.vision import Text
    records = [Text('Preset #1', (150, 254, 84, 21), 0.99)]
    header = team_vision.saved_team_header(records, (1920, 1080))
    assert header['slot'] == 1 and header['box'] == (150, 254, 84, 21)
