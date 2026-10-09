from copy import deepcopy
from pathlib import Path

import pytest

from maalimbus.reward_receipt_audit import verify
from maalimbus.storage import read_json

ROOT=Path(__file__).resolve().parents[1]


def test_incomplete_input_chain_refuses_without_any_frame_read(tmp_path):
    with pytest.raises(ValueError,match='intent chain missing'):
        verify({'scope':'run'},tmp_path/'absent.json',{})


def retained():
    transaction=ROOT/'config/user-reward-claim-transaction.json'
    names={'claim':'final-reward-authorized-claim-live','confirm':'final-reward-authorized-confirm-live',
           'receipt':'final-reward-receipt-ack-live','pass':'final-pass-receipt-ack-live'}
    paths={key:ROOT/f'build/{name}-20261008.json' for key,name in names.items()}
    home=ROOT/'evidence/runtime/window-20261008-172705/frame-0001.json'
    if not transaction.exists() or not home.exists() or any(not p.exists() for p in paths.values()):
        pytest.skip('Retained private runtime evidence is not distributed with source')
    tx=read_json(transaction)
    if tx.get('scope')!='d7c1499436f647208adc50860692a5c2':
        pytest.skip('Private transaction has advanced to another run')
    return tx,home,{k:read_json(p) for k,p in paths.items()}


def test_actual_receipt_chain_readonly():
    tx,home,reports=retained();original=deepcopy(tx)
    proof=verify(tx,home,reports)
    assert proof['actual_amount']==tx['receipt_visible_amount']
    assert proof['actual_pass_level']==tx['pass_level']
    assert proof['payout_received'] and not proof['state_written']
    assert tx==original


@pytest.mark.parametrize('fault',['scope','number','touch','frame','intent','count','target'])
def test_retained_chain_rejects_unbound_evidence(fault):
    tx,home,reports=retained()
    if fault=='scope':reports['claim']['run_ledger']['run']='another'
    if fault=='number':tx['receipt_visible_amount']+=1
    if fault=='touch':reports['claim']['steps'][0]['click_point']=[-1,-1]
    if fault=='frame':reports['claim']['steps'][0]['observation']['image_sha256']='changed'
    if fault=='intent':tx['confirm_sent']=False
    if fault=='count':reports['claim']['clicks_sent']=2
    if fault=='target':
        reports['claim']['steps'][0]['target']=[1,1,10,10]
        reports['claim']['steps'][0]['click_point']=[2,2]
    with pytest.raises(ValueError):verify(tx,home,reports)
