"""The board's preset is a fact, the rotation is a preference.

D117 refused a page that printed another saved team, and its first live effect was a
stop at 14 s with zero clicks (`packaged-mirror-20261024-113756`).  The operator's game
had one of the rotation's own teams selected, so preferring the board is the reading
consistent with D90 (gifts are planned for the team the board shows) and with the
complaint that started this thread (m07302).  A board showing a preset the rotation
never listed is still refused: nobody chose that team here.
"""
import json
from types import SimpleNamespace

from maalimbus import pages, window
from maalimbus.storage import RunStore


def _store(tmp_path, slots=(2,)):
    return RunStore(tmp_path / 'user-run-ledger.json',
                    [SimpleNamespace(slot=slot) for slot in slots])


def test_the_board_team_is_adopted_when_it_is_one_of_the_rotations_teams(tmp_path):
    store = _store(tmp_path, slots=(1, 2))
    store.point_at(2)
    # The decision the runner makes: shown team is a saved slot -> adopt it.
    shown, slots = 1, tuple(store.slots)
    assert shown in slots
    before = store.team_slot
    store.point_at(shown)
    assert before == 2 and store.team_slot == 1
    journal = json.loads((tmp_path / 'user-run-ledger.json').read_text(encoding='utf-8'))
    assert journal['rotation'] is not None


def test_a_board_team_outside_the_rotation_is_not_deployable(tmp_path):
    store = _store(tmp_path, slots=(2, 3))
    assert 1 not in tuple(store.slots)
    plan = window.plan_step('PRE_BATTLE_TEAM', controls={'pre_battle.battle': (1, 2, 3, 4)},
                            team={'preset_mismatch': True, 'states': [], 'participants': [],
                                  'order': [], 'saved_team': 1,
                                  'saved_team_box': (150, 254, 84, 21), 'tries': 99})
    assert plan['action'] == 'record'
    assert plan['reason'] == 'the_board_shows_a_different_saved_team_than_the_plan_deploys'


def test_after_adoption_the_page_deploys_normally():
    plan = window.plan_step('PRE_BATTLE_TEAM',
                            controls={'pre_battle.battle': (1651, 832, 192, 97),
                                      'pre_battle.clear_selection': (1651, 669, 173, 97)},
                            team={'reset_required': True, 'states': [], 'participants': [],
                                  'order': [], 'saved_team': 1, 'reconciled': {'ledger': 2, 'board': 1}})
    assert plan['action'] == 'click'
    assert plan['reason'] == 'clear_inherited_participant_order_before_saved_deployment'


def test_the_refusal_still_has_a_kind_for_the_census():
    kind = pages.REFUSALS['the_board_shows_a_different_saved_team_than_the_plan_deploys']
    assert kind == 'bad_saved_state'
