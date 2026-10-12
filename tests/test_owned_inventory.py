import pytest
from maalimbus.owned_inventory import build_index,reconcile_titles,owned_page


def test_index_separates_missing_facts_and_npc():
    x=build_index([dict(id=9999,title='NPC'),dict(id=10101,title='LCB Sinner'),
                   dict(id=10120,title='New identity')],dict(identities=[]),{})
    assert len(x['identities'])==2 and x['coverage']['live_complete'] is False
    assert x['identities'][1]['keywords'] is None
    r=reconcile_titles(x,1,[dict(title='LCB\nSinner',score=.99),
        dict(title='Unknown',score=.99)],'zh-CN')
    assert r['owned'][0]['id']==10101 and len(r['unresolved'])==1
    assert r['unobserved_ownership']=='unknown' and not r['inventory_complete']


def test_ambiguous_alias_and_cross_sinner_do_not_assign():
    x=build_index([dict(id=10101,title='Same'),dict(id=10102,title='Same'),
                  dict(id=10201,title='Other')],dict(identities=[]),{})
    assert not reconcile_titles(x,1,[dict(title='Same',score=.99),dict(title='Other',score=.99)],'zh-CN')['owned']


def test_actual_ryoshu_accent_header_is_not_a_different_sinner():
    assert owned_page(dict(size=[1920,1080],ocr=[dict(text='IDENTITIES:RYOSHÚ',
        box=[176,69,214,42],score=.959572)],owned_filter=dict(owned_checked=True,all_unchecked=True)))==4


@pytest.mark.parametrize('fault',['filter','header','confidence'])
def test_owned_page_requires_independent_header_and_filter(fault):
    r=dict(size=[1920,1080],ocr=[dict(text='IDENTITIES: YI SANG',box=[178,69,208,40],score=.99)],
           owned_filter=dict(owned_checked=True,all_unchecked=True))
    assert owned_page(r)==1
    if fault=='filter':r['owned_filter']['owned_checked']=False
    elif fault=='header':r['ocr'][0]['text']='Selected Identity'
    else:r['ocr'][0]['score']=.89
    with pytest.raises(ValueError):owned_page(r)
