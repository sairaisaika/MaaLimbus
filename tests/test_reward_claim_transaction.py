import pytest
import copy
from maalimbus.storage import write_json,read_json
from maalimbus.reward_claim_transaction import RewardClaimTransaction
from maalimbus.run_wiring import ledger_event,REWARD_CONFIRM_REASON,BONUS_CONFIRM_REASON

POLICY=dict(max_reward_modules=6,module_budget_pending=False,reward_budget_scope='run')
OFFER=dict(currency='enkephalin_modules',cost=6,weekly=1)
BALANCES=dict(modules=20,starlight=16)

@pytest.mark.parametrize('change',[{'max_reward_modules':0},{'max_reward_modules':5},
    {'max_reward_modules':True},{'module_budget_pending':True},{'reward_budget_scope':'old'}])
def test_unapproved_or_exceeded_budget_cannot_reserve(tmp_path,change):
    tx=RewardClaimTransaction(tmp_path/'tx.json')
    with pytest.raises(ValueError):tx.reserve('run',dict(POLICY,**change),OFFER,BALANCES,'before')
    assert not tx.path.exists()

@pytest.mark.parametrize('change',[{'currency':'lunacy'},{'cost':None},{'cost':True},
    {'cost':0},{'weekly':4}])
def test_unknown_currency_or_cost_cannot_reserve(tmp_path,change):
    tx=RewardClaimTransaction(tmp_path/'tx.json')
    with pytest.raises(ValueError):tx.reserve('run',POLICY,dict(OFFER,**change),BALANCES,'before')

def test_changed_offer_and_scope_cannot_commit_reserved_budget(tmp_path):
    tx=RewardClaimTransaction(tmp_path/'tx.json');tx.reserve('run',POLICY,OFFER,BALANCES,'before')
    for scope,offer in [('other',OFFER),('run',dict(OFFER,cost=18))]:
        with pytest.raises(ValueError):tx.claim_intent(scope,offer,'claim')
    assert tx.data['reserved_modules']==6 and not tx.data['claim_sent']

def test_restart_keeps_unknown_claim_and_confirmation_nonrepeatable(tmp_path):
    tx=RewardClaimTransaction(tmp_path/'tx.json');tx.reserve('run',POLICY,OFFER,BALANCES,'before')
    tx.claim_intent('run',OFFER,'claim')
    tx=RewardClaimTransaction(tx.path)
    with pytest.raises(ValueError):tx.claim_intent('run',OFFER,'retry')
    with pytest.raises(ValueError):tx.reserve('new',dict(POLICY,max_reward_modules=18),OFFER,BALANCES,'new')
    with pytest.raises(ValueError):tx.confirm_intent('run','confirm')
    tx.confirm_intent('run','confirm',question_proven=True)
    tx=RewardClaimTransaction(tx.path)
    with pytest.raises(ValueError):tx.confirm_intent('run','repeat',question_proven=True)
    assert tx.data['pending']=='confirm' and not tx.data['completed'] and not tx.data['reward_received']

@pytest.mark.parametrize('page,reason',[('RUN_REWARD_CONFIRM',REWARD_CONFIRM_REASON),
                                      ('RUN_REWARD_BONUS',BONUS_CONFIRM_REASON)])
def test_click_success_and_confirmation_cannot_unlock_rotation(page,reason):
    assert ledger_event(page=page,reason=reason,cleared=(1,2,3,4,5),victory=True) is None

@pytest.mark.parametrize('balances',[{'modules':5,'starlight':16},{'modules':20},
                                   {'modules':True,'starlight':16}])
def test_unproven_before_balance_cannot_reserve(tmp_path,balances):
    tx=RewardClaimTransaction(tmp_path/'tx.json')
    with pytest.raises(ValueError):tx.reserve('run',POLICY,OFFER,balances,'before')


def completed_transaction():
    return dict(scope='old',completed=True,reward_received=True,pending=None,
        claim_sent=True,confirm_sent=True,receipt_ack_sent=True,
        claim_proof='claim',confirm_proof='confirm',receipt_proof='receipt',
        home_return_proof='home',receipt_chain=[
            dict(frame='receipt',png_sha256='a'*64),dict(frame='home',png_sha256='b'*64)])


def test_completed_prior_scope_is_preserved_in_atomic_new_reservation(tmp_path):
    path=tmp_path/'tx.json';old=completed_transaction();write_json(path,old)
    tx=RewardClaimTransaction(path)
    tx.reserve('run',POLICY,dict(OFFER,cost=5,weekly=0),BALANCES,'new')
    assert read_json(path)['history']==[old]
    assert tx.data['scope']=='run' and tx.data['reserved_modules']==5
    assert not tx.data['reward_received'] and tx.data['pending']=='reserved'
    with pytest.raises(ValueError):tx.reserve('run',POLICY,OFFER,BALANCES,'repeat')


@pytest.mark.parametrize('fault',['pending','same_scope','receipt','home','hash','history'])
def test_unreconciled_or_reused_scope_never_archives_or_changes_file(tmp_path,fault):
    old=completed_transaction()
    if fault=='pending':old['pending']='confirm'
    if fault=='same_scope':old['scope']='run'
    if fault=='receipt':old.pop('receipt_proof')
    if fault=='home':old['home_return_proof']='unseen'
    if fault=='hash':old['receipt_chain'][0]['png_sha256']='invalid'
    if fault=='history':old['history']=[dict(scope='run')]
    path=tmp_path/'tx.json';write_json(path,old);before=path.read_bytes()
    with pytest.raises(ValueError):RewardClaimTransaction(path).reserve('run',POLICY,OFFER,BALANCES,'new')
    assert path.read_bytes()==before


def test_invalid_new_budget_does_not_archive_completed_transaction(tmp_path):
    path=tmp_path/'tx.json';write_json(path,completed_transaction());before=path.read_bytes()
    tx=RewardClaimTransaction(path);old=copy.deepcopy(tx.data)
    with pytest.raises(ValueError):tx.reserve('run',dict(POLICY,max_reward_modules=4),OFFER,BALANCES,'new')
    assert tx.data==old and path.read_bytes()==before
