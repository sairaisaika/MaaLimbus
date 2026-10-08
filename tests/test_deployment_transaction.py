import pytest
from maalimbus.deployment_transaction import DeploymentTransaction

def test_inherited_four_participants_are_cleared_before_saved_order(tmp_path):
    p=tmp_path/'deployment.json';order=[3,4,9,1,7,2,12,5,8,10,11,6]
    t=DeploymentTransaction(p)
    assert t.prepare('run',order,(4,12))['reset_required']
    t.intent('clear',(4,12))
    with pytest.raises(ValueError):DeploymentTransaction(p).prepare('run',order,(4,12))
    with pytest.raises(ValueError):t.observe((4,12))
    t.observe((0,12))
    for index,card in enumerate(order):
        assert not t.prepare('run',order,(index,12))['reset_required']
        with pytest.raises(ValueError):t.intent('card',(index,12),13)
        t.intent('card',(index,12),card);t.observe((index+1,12))
    assert t.prepare('run',order,(12,12))['order_verified']
    assert DeploymentTransaction(p).data['sequence']==order


def test_clear_confirmation_is_durable_and_never_repeated(tmp_path):
    p=tmp_path/'deployment.json';t=DeploymentTransaction(p)
    t.prepare('run',[3,4,9,1,7,2,12,5,8,10,11,6],(12,12));t.intent('clear',(12,12))
    with pytest.raises(ValueError):t.confirm_clear('other')
    t.confirm_clear('run')
    resumed=DeploymentTransaction(p)
    with pytest.raises(ValueError):resumed.confirm_clear('run')
    with pytest.raises(ValueError):resumed.observe((12,12))
    resumed.observe((0,12))
    assert resumed.data['pending'] is None
