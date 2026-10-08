import json
from pathlib import Path

import pytest

from maalimbus.floor_gifts import observe, rank
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text

ROOT=Path(__file__).resolve().parents[1]
FRAME=ROOT/'evidence/runtime/window-20261008-051724/frame-0032.json'


@pytest.fixture(scope='module')
def catalog():
    return GiftCatalog(ROOT/'assets/resource/base')


def words():
    data=json.loads(FRAME.read_text())
    return [Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']]


def test_real_offers_keep_display_title_and_bind_their_own_trials(catalog):
    offers,count=observe(words(),(1920,1080),catalog)
    assert count==dict(chosen=1,required=2)
    assert [(o.title,o.trial.level,o.trial.kind,o.trial.amount) for o in offers]==[
        ('Dimensional Recycle Bin',1,'defense',2),('Blue Zippo Lighter',1,'damage_reduction',5),
        ('Lithograph',2,'offense',1),('Golden Urn',1,'hp',5)]
    assert offers[0].canonical=='Dimensional Recycle Bi'
    ranked=rank(offers,Team(2,frozenset({'Charge','Tremor'})),['Dimensional Recycle Bin'])
    assert [r['title'] for r in ranked]==['Golden Urn','Blue Zippo Lighter','Lithograph']
    assert not any(r['preferred'] for r in ranked)


@pytest.mark.parametrize('text',['Defense Level +2','Mounting Trials','+2','Golden Urn','1/2'])
def test_missing_identity_trial_or_counter_refuses(catalog,text):
    with pytest.raises(ValueError):
        observe([r for r in words() if r.text!=text],(1920,1080),catalog)


def test_changed_buff_and_duplicate_effect_refuse(catalog):
    records=words()
    changed=[Text('Coin Power +9',r.box,r.score) if r.text=='Offense Level +1' else r for r in records]
    with pytest.raises(ValueError,match='unknown'):observe(changed,(1920,1080),catalog)
    records.append(next(r for r in records if r.text=='Max HP +5%'))
    with pytest.raises(ValueError,match='unique'):observe(records,(1920,1080),catalog)


def test_block_wins_and_team_synergy_is_bounded(catalog):
    offers,_=observe(words(),(1920,1080),catalog)
    team=Team(2,frozenset({'Charge'}),allow=frozenset({'Blue Zippo Lighter'}),block=frozenset({'Golden Urn'}))
    ranked=rank(offers,team,['Dimensional Recycle Bin'])
    assert ranked[0]['title']=='Blue Zippo Lighter' and ranked[0]['preferred']
    assert all(r['title']!='Golden Urn' for r in ranked)


def test_durable_intent_refuses_unknown_or_unchanged_postcondition(tmp_path,catalog):
    offers,_=observe(words(),(1920,1080),catalog)
    path=tmp_path/'transaction.json'
    tx=FloorGiftTransaction(path)
    tx.prepare('scope',offers,dict(chosen=0,required=2),'before')
    tx.intent(offers[0].title,dict(chosen=0,required=2),'intent')
    resumed=FloorGiftTransaction(path)
    with pytest.raises(ValueError):resumed.prepare('scope',offers,dict(chosen=0,required=2),'same')
    with pytest.raises(ValueError):resumed.observe_pick(offers,dict(chosen=0,required=2),'same')
    assert FloorGiftTransaction(path).data['pending']['title']==offers[0].title
    tx.observe_pick(offers,dict(chosen=1,required=2),'after')
    tx.prepare('scope',offers,dict(chosen=1,required=2),'resume')
    with pytest.raises(ValueError):tx.intent(offers[0].title,dict(chosen=1,required=2),'repeat')
    with pytest.raises(ValueError):tx.commit('early')
    tx.intent(offers[3].title,dict(chosen=1,required=2),'second')
    tx.observe_pick(offers,dict(chosen=2,required=2),'after-second')
    tx.commit('commit')
    with pytest.raises(ValueError):FloorGiftTransaction(path).prepare('scope',offers,dict(chosen=2,required=2),'repeat-commit')


def test_inherited_selection_and_changed_scope_never_bootstrap(tmp_path,catalog):
    offers,count=observe(words(),(1920,1080),catalog)
    tx=FloorGiftTransaction(tmp_path/'transaction.json')
    with pytest.raises(ValueError,match='without_scoped'):tx.prepare('scope',offers,count,'legacy')
    assert not tx.path.exists()
    tx.prepare('scope',offers,dict(chosen=0,required=2),'new')
    with pytest.raises(ValueError,match='unresolved'):tx.prepare('other',offers,dict(chosen=0,required=2),'other')


def test_explicit_legacy_migration_requires_scope_and_real_input_evidence(tmp_path,catalog):
    from maalimbus.floor_gift_transaction import adopt_legacy_single_pick
    result=FRAME.parent/'result.json'; scope='d7c1499436f647208adc50860692a5c2'
    tx=FloorGiftTransaction(tmp_path/'migrated.json')
    with pytest.raises(ValueError,match='scope'):
        adopt_legacy_single_pick(tx,result,ROOT/'evidence', 'wrong',catalog)
    assert not tx.path.exists()
    d=adopt_legacy_single_pick(tx,result,ROOT/'evidence',scope,catalog)
    assert d['selected']==['Dimensional Recycle Bin'] and d['pending'] is None
    assert not d['commit_sent'] and not d['completed'] and not d['receipts']
    with pytest.raises(ValueError):adopt_legacy_single_pick(tx,result,ROOT/'evidence',scope,catalog)


def test_receipts_keep_full_titles_and_require_each_named_successor(tmp_path,catalog):
    from maalimbus.floor_gift_transaction import adopt_legacy_single_pick
    tx=FloorGiftTransaction(tmp_path/'receipts.json')
    adopt_legacy_single_pick(tx,FRAME.parent/'result.json',ROOT/'evidence',
                             'd7c1499436f647208adc50860692a5c2',catalog)
    offers,_=observe(words(),(1920,1080),catalog)
    tx.intent('Golden Urn',dict(chosen=1,required=2),'second')
    tx.observe_pick(offers,dict(chosen=2,required=2),'selected')
    tx.commit('commit')
    with pytest.raises(ValueError):tx.receipt_intent('Dimensional Recycle Bi','truncated')
    tx.receipt_intent('Dimensional Recycle Bin','actual-full-title')
    with pytest.raises(ValueError):tx.receipt_intent('Dimensional Recycle Bin','repeat')
    with pytest.raises(ValueError):tx.observe_receipt('MAP',None,'missing-other-receipt')
    tx.observe_receipt('GIFT_GET','Golden Urn','next-named-receipt')
    tx.receipt_intent('Golden Urn','actual-second-receipt')
    tx.observe_receipt('THEME_PACKS',None,'next-floor-choice')
    assert tx.data['completed'] and tx.data['pending'] is None
    assert [r['title'] for r in tx.data['receipts']]==['Dimensional Recycle Bin','Golden Urn']


def test_floor_two_successor_identity_does_not_claim_mode():
    from maalimbus.theme_vision import selection_floor
    path=ROOT/'evidence/runtime/window-20261008-081512/frame-0005.json'
    data=json.loads(path.read_text());records=[Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']]
    assert selection_floor(records,data['size'])==2
    for required in ('Pack Search','Refresh','SELECT FLOOR 2 THEME PACK'):
        assert selection_floor([r for r in records if r.text!=required],data['size']) is None
    assert selection_floor([Text(r.text,r.box,.89) for r in records],data['size']) is None
    from maalimbus.window import plan_step
    plan=plan_step('THEME_PACKS',difficulty=None,controls={'theme_packs.pack_01':[1,1,30,30]})
    assert plan['action'] not in ('click','swipe')
