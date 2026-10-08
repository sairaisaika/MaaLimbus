from maalimbus.window import plan_step


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
