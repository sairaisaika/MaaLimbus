import json
import re
from pathlib import Path

import pytest

from maalimbus.floor_gifts import observe, rank
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text

ROOT=Path(__file__).resolve().parents[1]
FRAME=ROOT/'evidence/runtime/window-20261008-051724/frame-0032.json'
MOUNTING=ROOT/'evidence/runtime/window-20261012-034813/frame-0079.json'


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


def test_changed_buff_is_carried_unreadable_and_duplicate_effect_refuses(catalog):
    records=words()
    changed=[Text('Coin Power +9',r.box,r.score) if r.text=='Offense Level +1' else r for r in records]
    offers,count=observe(changed,(1920,1080),catalog)
    assert count==dict(chosen=1,required=2)
    carried={o.title:o for o in offers}['Lithograph']
    assert 'Coin Power +9' in carried.unpriced and carried.trial.kind=='unpriced'
    ranked=rank(offers,Team(2,frozenset({'Charge','Tremor'})),['Dimensional Recycle Bin'])
    assert ranked and 'Lithograph' not in [r['title'] for r in ranked]
    records.append(next(r for r in records if r.text=='Max HP +5%'))
    with pytest.raises(ValueError,match='unique'):observe(records,(1920,1080),catalog)


def test_a_page_whose_trials_all_miss_the_grammar_has_no_choice(catalog):
    def unreadable():
        out=[]
        for r in words():
            if re.search(r'Level \+|Max HP \+|Damage Taken',r.text):out.append(Text('Coin Power +9',r.box,r.score))
            else:out.append(r)
        return out
    offers,_=observe(unreadable(),(1920,1080),catalog)
    assert all(o.unpriced for o in offers)
    assert rank(offers,Team(2,frozenset({'Charge'})),[])==[]


def test_the_live_mounting_trials_page_prices_three_cards_and_carries_one(catalog):
    data=json.loads(MOUNTING.read_text())
    records=[Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']]
    offers,count=observe(records,tuple(data['size']),catalog)
    assert count==dict(chosen=0,required=2)
    assert [o.title for o in offers]==['Oracle','Bloody Gadget','Voodoo Doll','Blood, Sweat, and Tears']
    assert {o.title:o.unpriced for o in offers if o.unpriced}=={'Bloody Gadget':'Defense Skill Final Power'}
    ranked=[r['title'] for r in rank(offers,Team(5,frozenset({'Poise'})),[])]
    assert ranked==['Oracle','Voodoo Doll','Blood, Sweat, and Tears']
    # Evidence changes when the printed trial is read: the carried text is part of
    # the offer identity, so a later priced read is a new transaction, not a resume.
    repriced=[Text('Damage Taken -5%',r.box,r.score) if r.text=='Defense Skill Final Power' else r
              for r in records]
    other,_=observe(repriced,tuple(data['size']),catalog)
    assert FloorGiftTransaction.signature(other)!=FloorGiftTransaction.signature(offers)


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


NOTICE=ROOT/'evidence/runtime/pi-20261012-135557'


def _committed_two_pick_transaction(tmp_path,name='substituted.json'):
    """The retained real flow: one adopted pick, a second pick, then Select."""
    from maalimbus.floor_gift_transaction import adopt_legacy_single_pick
    catalog=GiftCatalog(ROOT/'assets/resource/base')
    tx=FloorGiftTransaction(tmp_path/name)
    adopt_legacy_single_pick(tx,FRAME.parent/'result.json',ROOT/'evidence',
                             'd7c1499436f647208adc50860692a5c2',catalog)
    offers,_=observe(words(),(1920,1080),catalog)
    tx.intent('Golden Urn',dict(chosen=1,required=2),'second',owned=True)
    tx.observe_pick(offers,dict(chosen=2,required=2),'selected')
    tx.commit('commit')
    return tx


def test_a_duplicate_pick_that_came_back_renamed_is_labelled_not_refused(tmp_path):
    """Live: the owned 'Portable Battery Socket' was answered with 'Faint Vestige'."""
    tx=_committed_two_pick_transaction(tmp_path)
    tx.receipt_intent('Dimensional Recycle Bin','first')
    label=tx.observe_receipt('GIFT_GET','Faint Vestige','renamed-successor')
    assert label==dict(expected='Golden Urn',printed='Faint Vestige',expected_owned=True,
                       proof='renamed-successor')
    assert tx.data['substitutions']==[label]
    assert [r['title'] for r in tx.data['receipts']]==['Dimensional Recycle Bin']
    assert not tx.data['completed']
    assert tx.data['pending']==dict(kind='commit',proof='renamed-successor',granted='Faint Vestige')
    # The renamed notice is the next pick's receipt, and it is still the run's own pick.
    tx.receipt_intent('Faint Vestige','renamed-intent')
    assert tx.data['pending']==dict(kind='receipt',title='Golden Urn',proof='renamed-intent',
                                    printed='Faint Vestige')
    tx.observe_receipt('MAP',None,'left')
    assert tx.data['completed'] and tx.data['pending'] is None
    assert [r['title'] for r in tx.data['receipts']]==['Dimensional Recycle Bin','Golden Urn']
    assert tx.data['receipts'][1]['printed']=='Faint Vestige'


def test_the_same_notice_coming_back_twice_is_still_refused(tmp_path):
    tx=_committed_two_pick_transaction(tmp_path)
    tx.receipt_intent('Dimensional Recycle Bin','first')
    with pytest.raises(ValueError,match='successor_not_proven'):
        tx.observe_receipt('GIFT_GET','Dimensional Recycle Bin','unchanged')


def test_a_stray_notice_after_every_pick_is_receipted_is_refused(tmp_path):
    tx=_committed_two_pick_transaction(tmp_path)
    tx.receipt_intent('Dimensional Recycle Bin','first')
    tx.observe_receipt('GIFT_GET','Golden Urn','next')
    tx.receipt_intent('Golden Urn','second')
    with pytest.raises(ValueError,match='successor_not_proven'):
        tx.observe_receipt('GIFT_GET','Faint Vestige','stray')


def test_the_live_renamed_notice_pair_reads_from_its_retained_frames():
    frame=NOTICE/'frame-0084.json'
    if not frame.exists():pytest.skip('retained live floor-gift notice evidence is not present')
    from maalimbus.floor_gift_transaction import retained_notice_name
    from maalimbus.initial_gifts import receipt_name
    assert retained_notice_name(frame,evidence_root=ROOT/'evidence/runtime')=='Prejudice'
    data=json.loads((NOTICE/'frame-0085.json').read_text())
    assert receipt_name([Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']],
                        data['size'])=='Faint Vestige'
    with pytest.raises(ValueError,match='outside_evidence'):
        retained_notice_name(frame,evidence_root=ROOT/'evidence/runtime/pi-20261012-123906')


def test_a_retained_notice_whose_image_changed_is_refused(tmp_path):
    frame=NOTICE/'frame-0084.json'
    if not frame.exists():pytest.skip('retained live floor-gift notice evidence is not present')
    from maalimbus.floor_gift_transaction import retained_notice_name
    copy=tmp_path/'frame-0084.json';copy.write_text(frame.read_text())
    image=tmp_path/'frame-0084.png';image.write_bytes((NOTICE/'frame-0084.png').read_bytes())
    assert retained_notice_name(copy,evidence_root=tmp_path)=='Prejudice'
    image.write_bytes(image.read_bytes()+b'\x00')
    with pytest.raises(ValueError,match='image_changed'):
        retained_notice_name(copy,evidence_root=tmp_path)
