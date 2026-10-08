import copy
import pytest
from maalimbus.paid_reward_action import prepare
from maalimbus.storage import write_json,read_json


def fixture(tmp_path):
    write_json(tmp_path/'user-mirror-settings.json', dict(max_reward_modules=6,
        module_budget_pending=False,reward_budget_scope='run'))
    write_json(tmp_path/'user-run-ledger.json',dict(active=dict(id='run',floors=[1,2,3,4,5],victory=True,reward=False)))
    return dict(scene='RUN_REWARD_DIALOG',size=[1920,1080],
        reward_cost=dict(currency='enkephalin_modules',cost=6,weekly=1),ocr=[
            dict(text='841',box=[1590,682,108,86],score=1),
            dict(text='Claim',box=[1250,798,100,40],score=1)])


def test_real_cost_scoped_intent_never_invents_balance_or_payout(tmp_path):
    record=fixture(tmp_path)
    assert prepare('claim',record,tmp_path,'run','actualframe')==[1250,798,100,40]
    tx=read_json(tmp_path/'user-reward-claim-transaction.json')
    assert tx['claim_sent'] and tx['before_balances']['modules'] is None
    assert tx['before_balances']['starlight'] is None and not tx['reward_received']
    with pytest.raises(ValueError):prepare('claim',record,tmp_path,'run','retry')


@pytest.mark.parametrize('fault',['cost','weekly','currency','scene','layout','stars','button','scope'])
def test_changed_or_missing_paid_offer_stops_before_intent(tmp_path,fault):
    r=fixture(tmp_path)
    if fault=='cost':r['reward_cost']['cost']=18
    if fault=='weekly':r['reward_cost']['weekly']=3
    if fault=='currency':r['reward_cost']['currency']='lunacy'
    if fault=='scene':r['scene']='UNKNOWN'
    if fault=='layout':r['size']=[1280,720]
    if fault=='stars':r['ocr'].pop(0)
    if fault=='button':r['ocr'].pop()
    with pytest.raises(ValueError):prepare('claim',r,tmp_path,'other' if fault=='scope' else 'run','frame')
    assert not (tmp_path/'user-reward-claim-transaction.json').exists()


def test_exact_confirmation_only_once_and_does_not_credit(tmp_path):
    prepare('claim',fixture(tmp_path),tmp_path,'run','before')
    r=dict(scene='RUN_REWARD_CONFIRM',size=[1920,1080],ocr=[
        dict(text='Claim the rewards?',box=[800,486,320,40],score=1),
        dict(text='Cancel',box=[704,720,140,40],score=1),
        dict(text='Confirm',box=[1116,720,112,40],score=1)])
    bad=copy.deepcopy(r);bad['ocr'][0]['text']='Spend currency?'
    with pytest.raises(ValueError):prepare('confirm',bad,tmp_path,'run','wrong')
    assert prepare('confirm',r,tmp_path,'run','confirm')==[1116,720,112,40]
    with pytest.raises(ValueError):prepare('confirm',r,tmp_path,'run','retry')
    assert not read_json(tmp_path/'user-reward-claim-transaction.json')['reward_received']


def test_acquired_receipt_requires_its_title_amount_and_prior_confirm(tmp_path):
    prepare('claim',fixture(tmp_path),tmp_path,'run','before')
    tx=read_json(tmp_path/'user-reward-claim-transaction.json')
    tx.update(confirm_sent=True,pending='confirm')
    write_json(tmp_path/'user-reward-claim-transaction.json',tx)
    r=dict(scene='RUN_CLAIM',size=[1920,1080],ocr=[
        dict(text='Rewards Acquired',box=[800,353,318,40],score=1),
        dict(text='250',box=[948,534,66,51],score=1),
        dict(text='Confirm',box=[876,682,170,48],score=1)])
    bad=copy.deepcopy(r);bad['ocr'][0]['text']='Rewards Offered'
    with pytest.raises(ValueError):prepare('receipt',bad,tmp_path,'run','wrong')
    assert prepare('receipt',r,tmp_path,'run','receipt')==[876,682,170,48]
    with pytest.raises(ValueError):prepare('receipt',r,tmp_path,'run','repeat')
    assert not read_json(tmp_path/'user-reward-claim-transaction.json')['reward_received']


def test_actual_wrapped_weekly_question_requires_full_words(tmp_path):
    prepare('claim',fixture(tmp_path),tmp_path,'run','before')
    r=dict(scene='RUN_REWARD_BONUS',size=[1920,1080],ocr=[
        dict(text="Spend your 'Weekly Bonuses, to claim the bonus",box=[636,486,646,34],score=.978),
        dict(text='rewards?',box=[890,522,138,33],score=1),
        dict(text='X Cancel',box=[706,720,138,36],score=.939),
        dict(text='Confirm',box=[1112,720,112,34],score=1)])
    bad=copy.deepcopy(r);bad['ocr'].pop(1)
    with pytest.raises(ValueError):prepare('confirm',bad,tmp_path,'run','incomplete')
    assert prepare('confirm',r,tmp_path,'run','weeklyconfirm')==[1112,720,112,34]
    assert not read_json(tmp_path/'user-reward-claim-transaction.json')['reward_received']


def test_pass_receipt_independent_full_title_level_and_xp(tmp_path):
    prepare('claim',fixture(tmp_path),tmp_path,'run','before')
    tx=read_json(tmp_path/'user-reward-claim-transaction.json')
    tx.update(confirm_sent=True,receipt_ack_sent=True)
    write_json(tmp_path/'user-reward-claim-transaction.json',tx)
    r=dict(scene='RUN_CLAIM',size=[1920,1080],ocr=[
        dict(text='Pass Level Up',box=[830,353,258,40],score=.992),
        dict(text='Pass Level',box=[592,464,110,28],score=1),
        dict(text='81',box=[596,494,106,113],score=.999),
        dict(text='Battle Pass XP',box=[782,470,242,40],score=1),
        dict(text='Confirm',box=[882,680,164,48],score=1)])
    bad=copy.deepcopy(r);bad['ocr'].pop(3)
    with pytest.raises(ValueError):prepare('pass',bad,tmp_path,'run','missingxp')
    assert prepare('pass',r,tmp_path,'run','pass')==[882,680,164,48]
    with pytest.raises(ValueError):prepare('pass',r,tmp_path,'run','repeat')
