from maalimbus.window import plan_step, successor_ok
from maalimbus.team_vision import selected_saved_team
from maalimbus.vision import Text


def test_team_two_follows_the_saved_charge_tremor_order_and_hong_lu_last():
    order=[3,4,9,1,7,2,12,5,8,10,11,6]
    controls={f'pre_battle.card_{i:02d}':[i*10,100,8,8] for i in range(1,13)}
    states=[None]*12
    for picked,card in enumerate(order):
        plan=plan_step('PRE_BATTLE_TEAM',controls=controls,
                       team={'states':states,'participants':[picked,12],'order':order})
        assert plan['detail']['card_index']==card
        states[card-1]='selected' if picked<7 else 'backup'


def test_broken_saved_order_does_not_choose_a_default_card():
    plan=plan_step('PRE_BATTLE_TEAM',controls={'pre_battle.card_01':[1,2,3,4]},
                   team={'states':[None]*12,'participants':[0,12],'order':[1]*12})
    assert plan['reason']=='saved_deployment_order_invalid'


def test_normal_or_unproven_mode_never_drags_a_pack():
    for mode in (None,'normal','unknown'):
        plan=plan_step('THEME_PACKS', difficulty=mode,
                       controls={'theme_packs.pack_01':[520,390,250,300],'theme_packs.pull_to':[600,980,100,30]})
        assert plan['reason']=='hard_difficulty_not_proven'
        assert not plan.get('target')


def test_selected_team_two_is_the_header_not_preset_one_or_sidebar_rows():
    records=[Text('TEAMS #2',(336,176,120,28),.99),
             Text('Preset #1',(150,255,110,24),.99),
             Text('TEAMS #1',(150,450,120,28),.99)]
    assert selected_saved_team(records,(1920,1080))==2
    assert selected_saved_team(records[1:],(1920,1080)) is None


def test_confirm_requires_actual_wanted_header_when_no_slot_target_exists():
    plan=plan_step('DUNGEON_TEAM',controls={'team.confirm_button':[1600,840,170,50]},
                   team={'wanted':2,'selected':1})
    assert plan['reason']=='wanted_team_header_not_proven'


def test_entry_dialog_may_reach_the_actual_loadout_picker():
    plan=plan_step('ENTRY_CONFIRM',controls={'entry_confirm.confirm_button':[1124,704,90,42]})
    assert successor_ok(plan,'DUNGEON_TEAM')
