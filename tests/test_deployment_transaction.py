import pytest
from maalimbus.deployment_transaction import DeploymentTransaction

def test_inherited_four_participants_are_cleared_before_saved_order(tmp_path):
    p=tmp_path/'deployment.json';order=[3,4,9,1,7,2,12,5,8,10,11,6]
    t=DeploymentTransaction(p)
    assert t.prepare('run',order,(4,12),[1,2,3,4]+[None]*8)['reset_required']
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


def test_wrong_order_is_changed_but_unread_digits_are_reread(tmp_path):
    t=DeploymentTransaction(tmp_path/'deployment.json')
    assert t.prepare('run',ORDER,(12,12),printed(list(reversed(ORDER))))['reset_required'] is True
    for digits in ([None]*12,None):
        uncertain=t.prepare('run',ORDER,(12,12),digits)
        assert not uncertain['reset_required'] and uncertain['order_uncertain']
        assert not uncertain['order_verified']
    assert t.prepare('run',ORDER,(12,12),printed(ORDER))['reset_required'] is False
    # A half-read page proves only the part it printed, positions 1..picked.
    half=[None]*12
    for position,card in enumerate(ORDER[:4],start=1):half[card-1]=position
    assert t.prepare('run',ORDER,(4,12),half)['reset_required'] is False
    broken=list(half);broken[ORDER[2]-1]=None
    uncertain=t.prepare('run',ORDER,(4,12),broken)
    assert not uncertain['reset_required'] and uncertain['order_uncertain']


def test_a_revive_is_booked_only_against_the_shop_counters_own_delta(tmp_path):
    # The only receipt that proves a revive happened is the shop's own counter moving by
    # exactly the price its modal printed (live 2026-10-12: 3093 -> 2993 for card 6's 100).
    p=tmp_path/'deployment.json';t=DeploymentTransaction(p);t.prepare('run',ORDER,(0,12))
    assert t.revived_cards()==[]
    assert t.book_revive(6,100,3093,2993,proof=dict(source='shop_currency_delta')) is True
    assert t.revived_cards()==[6]
    # The store on disk is what the next shop visit reads, and a second receipt for the same
    # card is the same fact, never a second revive.
    assert DeploymentTransaction(p).revived_cards()==[6]
    assert t.book_revive(6,100,2993,2893) is True
    assert t.revived_cards()==[6]
    for bad in (dict(cost=100,coins_before=3093,coins_after=3000),
                dict(cost=0,coins_before=3093,coins_after=3093),
                dict(cost=100,coins_before=3093,coins_after=None),
                dict(card=13,cost=100,coins_before=3093,coins_after=2993),
                dict(card=None,cost=100,coins_before=3093,coins_after=2993)):
        args=dict(card=6,cost=100,coins_before=3093,coins_after=2993);args.update(bad)
        with pytest.raises(ValueError):t.book_revive(**args)
    with pytest.raises(ValueError):DeploymentTransaction(tmp_path/'none.json').book_revive(
        6,100,3093,2993)


def test_a_revive_receipt_outlives_the_rewrite_that_clears_the_selection(tmp_path):
    # A submitted page makes the next prepare() rewrite the store from scratch (that is how the
    # selection is cleared).  A booked revive is a payment the shop already took, so the rewrite
    # must carry it: otherwise the next shop visit of the same run reads the dead slot again and
    # walks back into a picker it has already paid for.
    p=tmp_path/'deployment.json';t=DeploymentTransaction(p);t.prepare('run',ORDER,(12,12))
    assert t.book_revive(6,100,3093,2993,proof=dict(source='shop_currency_delta')) is True
    t.data['submitted']=True
    t.prepare('run',ORDER,(12,12))
    assert t.data['submitted'] is False
    assert t.revived_cards()==[6]
    assert DeploymentTransaction(p).revived_cards()==[6]


def test_a_new_run_does_not_inherit_the_previous_runs_receipts(tmp_path):
    # The shop is paid in the run's own currency, so a receipt booked under another scope proves
    # nothing about this run: the dead slot it named has to be read and paid for again.
    p=tmp_path/'deployment.json';t=DeploymentTransaction(p);t.prepare('run-a',ORDER,(12,12))
    assert t.book_revive(6,100,3093,2993) is True
    t.prepare('run-b',ORDER,(12,12))
    assert t.revived_cards()==[]
    assert DeploymentTransaction(p).revived_cards()==[]
