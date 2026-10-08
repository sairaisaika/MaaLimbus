import pytest
from maalimbus.grace_transaction import GraceTransaction
from maalimbus.window import plan_step


def test_purchase_survives_restart_and_unverified_input_stays_pending(tmp_path):
    p=tmp_path/'transaction.json';t=GraceTransaction(p)
    t.begin('run-a',[2,4,5,7],100,'entry.png')
    t.intent(2,10,116,'before.png')
    t=GraceTransaction(p)
    with pytest.raises(ValueError,match='pending'):t.validate('run-a',[2,4,5,7],100,116)
    with pytest.raises(ValueError):t.observe(116,'nochange.png')
    assert GraceTransaction(p).data['pending']['card']==2
    t.observe(106,'after.png')
    t=GraceTransaction(p)
    assert t.validate('run-a',[2,4,5,7],100,106)['selected']==[2]
    with pytest.raises(ValueError):t.intent(2,10,106,'repeat.png')
    with pytest.raises(ValueError):t.validate('run-b',[2,4,5,7],100,106)
    with pytest.raises(ValueError):t.validate('run-a',[2,4,5,7],100,90)


def test_confirmation_requires_complete_transaction_and_no_conversion():
    c={'star_confirm.confirm_button':[1034,778,154,35],
       'star_confirm.cancel_button':[740,774,146,41]}
    assert plan_step('STAR_CONFIRM',controls=c)['action']=='record'
    assert plan_step('STAR_CONFIRM',controls=c,graces={'incomplete':True})['reason']=='incomplete_graces_return_to_selection'
    assert plan_step('STAR_CONFIRM',controls=c,graces={'complete':True,'conversion':'unchecked','cost':430})['action']=='record'
    assert plan_step('STAR_CONFIRM',controls=c,graces={'complete':True,'conversion':'unchecked','cost':0})['action']=='click'
