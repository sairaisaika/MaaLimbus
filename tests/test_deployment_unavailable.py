import pytest
from maalimbus.deployment_transaction import DeploymentTransaction
from maalimbus.window import plan_step
ORDER=[6,2,4,9,12,7,11,10,3,1,8,5]
PROOF=dict(accepted=True,image_sha256='actual-hash',frame='actual-frame',unavailable=[6],participants=[0,11])

def test_dead_card_noop_recovery_preserves_saved_order_and_selects_remaining(tmp_path):
    t=DeploymentTransaction(tmp_path/'tx.json');t.prepare('run',ORDER,(0,12));t.intent('card',(0,11),6)
    original=list(ORDER)
    t.reconcile_unavailable('run',(0,11),[6],PROOF)
    state=t.prepare('run',ORDER,(0,11),unavailable=[6],availability_proof=PROOF)
    assert ORDER==original and t.data['saved_order']==ORDER and t.data['sequence']==[]
    assert t.data['rejected_unavailable_inputs'][0]['selected'] is False
    assert state['order']==ORDER[1:]
    states=[None]*12
    for picked,card in enumerate(ORDER[1:]):
        state=t.prepare('run',ORDER,(picked,11),unavailable=[6],availability_proof=PROOF)
        plan=plan_step('PRE_BATTLE_TEAM',controls={f'pre_battle.card_{i:02d}':[i,1,1,1] for i in ORDER},
                       team=dict(state,states=states,participants=[picked,11]))
        assert plan['detail']['card_index']==card
        t.intent('card',(picked,11),card);t.observe((picked+1,11));states[card-1]='selected'
    assert t.prepare('run',ORDER,(11,11),unavailable=[6],availability_proof=PROOF)['order_verified']

@pytest.mark.parametrize('scope,count,dead,proof',[
    ('foreign',(0,11),[6],PROOF),('run',(1,11),[6],PROOF),('run',(0,11),[2],PROOF),
    ('run',(0,11),[6],{}),('run',(0,11),[6],dict(PROOF,accepted=False))])
def test_uncertain_attempt_preserves_pending_bytes(tmp_path,scope,count,dead,proof):
    p=tmp_path/'tx.json';t=DeploymentTransaction(p);t.prepare('run',ORDER,(0,12));t.intent('card',(0,11),6)
    before=p.read_bytes()
    with pytest.raises(ValueError):t.reconcile_unavailable(scope,count,dead,proof)
    assert p.read_bytes()==before

def test_filtered_inherited_order_needs_no_clear_and_revived_next_encounter_uses_saved(tmp_path):
    t=DeploymentTransaction(tmp_path/'tx.json');numbers=[None]*12
    for position,card in enumerate(ORDER[1:],1):numbers[card-1]=position
    result=t.prepare('run',ORDER,(11,11),numbers,[6],PROOF)
    assert result['inherited_order'] and not result['reset_required'] and result['order_verified']
    t.data['submitted']=True
    assert t.prepare('run',ORDER,(0,12))['order']==ORDER

def test_capacity_alone_never_infers_missing_person(tmp_path):
    with pytest.raises(ValueError):DeploymentTransaction(tmp_path/'tx.json').prepare('run',ORDER,(0,11))
