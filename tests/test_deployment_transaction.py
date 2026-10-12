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


ORDER=[3,4,9,1,7,2,12,5,8,10,11,6]


def printed(order):
    """The numbers the page prints when it already carries ``order``."""
    numbers=[None]*12
    for position,card in enumerate(order,start=1):numbers[card-1]=position
    return numbers


def test_a_page_that_prints_the_saved_order_is_submitted_without_clearing(tmp_path):
    # The game keeps the previous encounter's deployment, so the second battle of a run
    # needs no Clear Selection at all: the printed numbers already prove the order.
    t=DeploymentTransaction(tmp_path/'deployment.json')
    state=t.prepare('run',ORDER,(12,12),printed(ORDER))
    assert state['reset_required'] is False
    assert state['order_verified'] is True
    assert state['inherited_order'] is True
    assert t.data['sequence']==[]
    assert state['assignment']==printed(ORDER)


def test_another_encounters_order_and_an_unread_page_are_still_cleared(tmp_path):
    t=DeploymentTransaction(tmp_path/'deployment.json')
    assert t.prepare('run',ORDER,(12,12),printed(list(reversed(ORDER))))['reset_required'] is True
    assert t.prepare('run',ORDER,(12,12),[None]*12)['reset_required'] is True
    assert t.prepare('run',ORDER,(12,12))['reset_required'] is True
    assert t.prepare('run',ORDER,(12,12),printed(ORDER))['reset_required'] is False
    # A half-read page proves only the part it printed, positions 1..picked.
    half=[None]*12
    for position,card in enumerate(ORDER[:4],start=1):half[card-1]=position
    assert t.prepare('run',ORDER,(4,12),half)['reset_required'] is False
    broken=list(half);broken[ORDER[2]-1]=None
    assert t.prepare('run',ORDER,(4,12),broken)['reset_required'] is True
