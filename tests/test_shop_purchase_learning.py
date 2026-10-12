"""Outcome collection is independent of successful execution and gift strength."""
import sys,json,hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from test_shop_transaction import setup,reserve,frame,shelf,question
from maalimbus.shop_outcomes import sync
from maalimbus.gift_plan import shop_wanted
from maalimbus.policies import Team
from maalimbus.storage import write_json,read_json


def purchase(tmp_path):
    tx,before=setup(tmp_path);reserve(tx,before)
    tx.reserve_confirm('scope','floor1:shop1',frame(tmp_path,'question',question(),'SHOP_PURCHASE'))
    tx.reconcile_purchase('scope','floor1:shop1',frame(tmp_path,'after',shelf(('Scalpel',),80)))
    return tx


def test_verified_purchase_labels_execution_but_not_strength_and_is_idempotent(tmp_path):
    tx=purchase(tmp_path);root=tmp_path/'review';before=tx.path.read_bytes()
    samples=sync(tx,root);assert len(samples)==1
    assert not samples[0]['training_eligible'] and samples[0]['outcomes']==[]
    record=read_json(samples[0]['sample'])
    assert record['action_executed'] and record['gift_causal_strength'] is None
    assert sync(tx,root)==samples and tx.path.read_bytes()==before
    assert len(list(root.glob('*/sample.json')))==1
    write_json(Path(samples[0]['sample']).parent/'review.json',{'status':'rejected'})
    assert sync(tx,root)==[]


def test_changed_purchase_proof_cannot_teach_value(tmp_path):
    tx=purchase(tmp_path);path=Path(tx.data['bought'][0]['successor']['path'])
    path.with_suffix('.png').write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash'):sync(tx,tmp_path/'review')


@pytest.mark.parametrize('scope',['scope','other_scope'])
def test_later_outcome_is_bound_to_exact_episode_and_copied_for_review(tmp_path,scope):
    # Set timestamp before reserving a separate transaction so the retained hash
    # stays immutable; this test's receipt simulates a prior well-bound action.
    from maalimbus.shop_transaction import ShopTransaction
    (tmp_path/'timed').mkdir()
    before=frame(tmp_path/'timed','before',shelf())
    payload=read_json(before);payload['utc']='2026-10-12T12:00:00+00:00';write_json(before,payload)
    tx2=ShopTransaction(tmp_path/'timed/transaction.json');tx2.begin_visit('scope','floor1:shop1',before)
    reserve(tx2,before)
    tx2.reconcile_purchase('scope','floor1:shop1',frame(tmp_path/'timed','after',shelf(('Scalpel',),80)))
    event=frame(tmp_path,'floor',[],'THEME_PACKS')
    payload=read_json(event);payload['utc']='2026-10-12T13:00:00+00:00';write_json(event,payload)
    ledger=tmp_path/'ledger.json'
    write_json(ledger,dict(version=1,active=dict(id=scope,events=dict(clear=dict(kind='floor_clear',
        floor=1,evidence=str(event),sha256=hashlib.sha256(event.read_bytes()).hexdigest()))),receipts=[]))
    sample=sync(tx2,tmp_path/'review',ledger)[0]
    assert len(sample['outcomes'])==(1 if scope=='scope' else 0)
    assert not sample['training_eligible']
    if scope=='scope':
        assert len(list(Path(sample['sample']).parent.glob('outcome-*.png')))==1
        event.write_bytes(event.read_bytes()+b' ')
        with pytest.raises(ValueError,match='proof changed'):sync(tx2,tmp_path/'review',ledger)


def test_utility_priority_enters_candidates_before_keyword_filter_and_block_wins():
    catalog=SimpleNamespace(entries={'Prestige Card':{'keywords':['Keywordless']},
                                    'Poise Gift':{'keywords':['Poise']}})
    team=Team(7,frozenset({'Poise'}))
    assert shop_wanted(team,catalog,{'Prestige Card':100})==['Prestige Card','Poise Gift']
    team=Team(7,frozenset({'Poise'}),block=frozenset({'Prestige Card'}))
    assert shop_wanted(team,catalog,{'Prestige Card':100})==['Poise Gift']
    with pytest.raises(ValueError):shop_wanted(team,catalog,{'Invented Gift':100})
