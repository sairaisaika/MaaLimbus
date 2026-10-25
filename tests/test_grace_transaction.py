import pytest
from maalimbus.grace_transaction import GraceTransaction
from maalimbus.window import plan_step


def test_explicit_saved_entry_settings_adoption_keeps_original_stub(tmp_path):
    t=GraceTransaction(tmp_path/'entry.json');t.begin('run',[1,3,5,6,8],0,'entry.png')
    proof=dict(page='STAR_GRACES',scope='run',frame_sha256='a'*64,configuration_sha256='b'*64)
    t.adopt_unspent_entry_settings('run',[2,4,5,7],100,116,proof)
    assert t.validate('run',[2,4,5,7],100,116)['entry_settings_adopted']['previous_budget']==0
    assert t.data['proofs']==['entry.png'] and t.data['selected']==[]
    with pytest.raises(ValueError):t.adopt_unspent_entry_settings('run',[2],100,116,proof)


@pytest.mark.parametrize('fault',['pending','selected','spent','available','budget','scope','proof'])
def test_entry_settings_cannot_erase_any_purchase_or_unknown_state(tmp_path,fault):
    t=GraceTransaction(tmp_path/'entry.json');t.begin('run',[1],0,'entry.png')
    proof=dict(page='STAR_GRACES',scope='run',frame_sha256='a'*64,configuration_sha256='b'*64)
    if fault=='pending':t.data['pending']=dict(card=1)
    if fault=='selected':t.data['selected']=[1]
    if fault=='spent':t.data['spent']=10
    if fault=='available':t.data['available']=116
    if fault=='budget':t.data['budget']=100
    if fault=='proof':proof['page']='UNKNOWN'
    with pytest.raises(ValueError):t.adopt_unspent_entry_settings('other' if fault=='scope' else 'run',[2],100,116,proof)


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


def test_a_wish_list_the_page_cannot_pay_for_narrows_onto_its_affordable_prefix(tmp_path):
    # Live 2026-10-12 01:56: the Graces page offered 60 starlight while the configured
    # set costs 100, so 2,4,5 were bought and the run then refused the page forever.
    # The cards this run already paid for stay in the plan and only the tail is dropped.
    p=tmp_path/'transaction.json';t=GraceTransaction(p)
    t.begin('run',[2,4,5,7],100,'entry.png')
    costs=[10,10,20,20,30,30,40,40,50,60]
    assert t.seal_affordable('run',[2,4,5,7],100,60,costs,'board.png')==[2,4,5]
    assert t.validate('run',[2,4,5],100,0)['requested']==[2,4,5]
    # The seal is durable and never re-budgets: a later round gets the frozen plan back.
    assert GraceTransaction(p).seal_affordable('run',[2,4,5,7],100,40,costs,'later.png')==[2,4,5]
    # A selection that is already part bought narrows onto what was actually paid for.
    t2=GraceTransaction(tmp_path/'part.json');t2.begin('run',[2,4,5,7],100,'entry.png')
    t2.data.update(selected=[2,4,5],spent=60)
    assert t2.seal_affordable('run',[2,4,5,7],100,60,costs,'after.png')==[2,4,5]
    # An unknown scope, an unverified purchase and an empty affordable set all refuse.
    t3=GraceTransaction(tmp_path/'other.json');t3.begin('run',[2,4,5,7],100,'entry.png')
    with pytest.raises(ValueError,match='scope'):
        t3.seal_affordable('other',[2,4,5,7],100,60,costs,'x.png')
    t3.data['pending']=dict(card=2)
    with pytest.raises(ValueError,match='pending'):
        t3.seal_affordable('run',[2,4,5,7],100,60,costs,'x.png')
    t4=GraceTransaction(tmp_path/'none.json');t4.begin('run',[10],100,'entry.png')
    with pytest.raises(ValueError,match='fits the current balance'):
        t4.seal_affordable('run',[10],100,5,costs,'x.png')


def test_confirmation_requires_complete_transaction_and_no_conversion():
    c={'star_confirm.confirm_button':[1034,778,154,35],
       'star_confirm.cancel_button':[740,774,146,41]}
    assert plan_step('STAR_CONFIRM',controls=c)['action']=='record'
    assert plan_step('STAR_CONFIRM',controls=c,graces={'incomplete':True})['reason']=='incomplete_graces_return_to_selection'
    assert plan_step('STAR_CONFIRM',controls=c,graces={'complete':True,'conversion':'unchecked','cost':430})['action']=='record'
    assert plan_step('STAR_CONFIRM',controls=c,graces={'complete':True,'conversion':'unchecked','cost':0})['action']=='click'


def test_a_ledger_that_spent_its_whole_budget_is_rebound_by_the_next_run(tmp_path):
    # Live evidence/runtime/packaged-mirror-20261025-053423: a new run inherited a ledger
    # with scope 37fc4d01..., budget 100, spent 100, pending None, and ended on
    # `Grace transaction scope or configuration mismatch` before reading a frame.  A plan
    # that spent its whole budget has nothing left to carry, so the next run owns the
    # ledger; a part-way plan still contradicts a new scope (the test above).
    p = tmp_path / 'transaction.json'
    t = GraceTransaction(p)
    t.begin('run-a', [2, 4, 5], 20, 'entry.png')
    t.intent(2, 10, 116, 'before.png')
    t.observe(106, 'after.png')
    t.intent(4, 10, 96, 'before.png')
    t.observe(86, 'after.png')
    assert t.data['spent'] == 20
    data = GraceTransaction(p).validate('run-b', [2, 4, 5], 20, 86)
    assert data['scope'] == 'run-b'
    assert data['spent'] == 0 and data['selected'] == [] and data['available'] is None
    assert data['scope_rebinds'][0]['was'] == 'run-a'
