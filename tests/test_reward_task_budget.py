from copy import deepcopy
import pytest
from maalimbus.reward_task_budget import apply
from maalimbus.storage import read_json,write_json


def setup(config):
    write_json(config/'user-run-ledger.json',dict(active=dict(id='current',team=7,
        floors=[1,2,3,4,5],victory=True,reward=False)))
    policy=dict(max_reward_modules=6,module_budget_pending=False,reward_budget_scope='old',
                max_lunacy_refills=0,conversion_budget=0,weekly_bonuses=0,unrelated={'kept':True})
    write_json(config/'user-mirror-settings.json',policy)
    write_json(config/'user-reward-claim-transaction.json',dict(scope='old',completed=True,pending=None))
    return policy


def test_saved_selection_never_loads_or_creates_state(tmp_path):
    assert not apply(tmp_path,'saved') and not list(tmp_path.iterdir())


@pytest.mark.parametrize('maximum',[0,5,6])
def test_explicit_current_budget_preserves_other_resources_and_transaction(tmp_path,maximum):
    policy=setup(tmp_path);tx=tmp_path/'user-reward-claim-transaction.json';before=tx.read_bytes()
    assert apply(tmp_path,maximum)
    expected=dict(policy,max_reward_modules=maximum,reward_budget_scope='current',module_budget_pending=maximum==0)
    assert read_json(tmp_path/'user-mirror-settings.json')==expected
    assert tx.read_bytes()==before
    assert not apply(tmp_path,maximum)


@pytest.mark.parametrize('fault',['missing_floor','unpaid_unknown','victory_false','active_none','pending','claim_sent','old_incomplete','invalid_cap','boolean'])
def test_invalid_budget_or_pending_claim_preserves_policy_bytes(tmp_path,fault):
    setup(tmp_path);ledger=read_json(tmp_path/'user-run-ledger.json');tx=read_json(tmp_path/'user-reward-claim-transaction.json');maximum=5
    if fault=='missing_floor':ledger['active']['floors']=[1,2,3,4]
    if fault=='unpaid_unknown':ledger['active'].pop('reward')
    if fault=='victory_false':ledger['active']['victory']=False
    if fault=='active_none':ledger['active']=None
    if fault=='pending':tx['pending']='confirm'
    if fault=='claim_sent':tx.update(scope='current',claim_sent=True)
    if fault=='old_incomplete':tx['completed']=False
    if fault=='invalid_cap':maximum=7
    if fault=='boolean':maximum=True
    write_json(tmp_path/'user-run-ledger.json',ledger);write_json(tmp_path/'user-reward-claim-transaction.json',tx)
    path=tmp_path/'user-mirror-settings.json';before=path.read_bytes()
    with pytest.raises(ValueError):apply(tmp_path,maximum)
    assert path.read_bytes()==before
