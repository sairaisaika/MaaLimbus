"""The real Purchase modal is not a shelf or an acquired receipt."""
import json,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from maalimbus.shop_vision import native_purchase_dialog,matching_purchase_question
from maalimbus.vision import Text,classify
from maalimbus.shop_native import repair_purchase_balances


def rows():
    return [Text('Purchase E.G.O Gifts',(674,236,292,34),.9988),
        Text('Purchase',(1092,706,128,34),1),Text('X Cancel',(710,702,156,42),.9121),
        Text("Devil's Share",(546,579,178,34),.9995),
        Text('2707',(1230,236,53,34),.953),Text('2563',(1305,235,57,35),.999)]


def test_full_effect_description_is_not_needed_to_identify_selected_purchase():
    r=rows();root=Path(__file__).resolve().parents[1]
    locale=json.loads((root/'assets/resource/en/locale.json').read_text(encoding='utf-8'))
    assert classify(r,locale,[1920,1080])=='SHOP_PURCHASE'
    assert matching_purchase_question(r,"Devil's Share",144,coins=2707)==[1092,706,128,34]
    for name,price,coins in [('Prestige Card',144,2707),("Devil's Share",145,2707),("Devil's Share",144,2708)]:
        assert matching_purchase_question(r,name,price,coins=coins) is None


@pytest.mark.parametrize('remove',[0,1,2,3,4,5])
def test_missing_header_control_name_or_quote_cannot_authorize_purchase(remove):
    r=rows();r.pop(remove)
    assert matching_purchase_question(r,"Devil's Share",144,coins=2707) is None


def test_purchase_confirmation_accepts_the_native_get_notice_as_successor():
    from maalimbus.window import plan_step
    p=plan_step('SHOP_PURCHASE',shop={'confirm':[1092,706,128,34]})
    assert 'GIFT_GET' in p['expect']


@pytest.mark.parametrize('badge', ['correct','missing','wrong_column','low','duplicate'])
def test_only_the_own_unique_purchased_badge_can_settle_retained_card(tmp_path,badge):
    from test_shop_transaction import setup,reserve,frame,shelf,question,row
    tx,before=setup(tmp_path);reserve(tx,before)
    tx.reserve_confirm('scope','floor1:shop1',frame(tmp_path,'dialog',question(),'SHOP_PURCHASE'))
    records=shelf(coins=80)
    mark=row('Purchased',(870,320,120,40))
    if badge=='wrong_column':mark['box'][0]+=230
    if badge=='low':mark['score']=.899
    if badge!='missing':records.append(mark)
    if badge=='duplicate':records.append(dict(mark))
    after=frame(tmp_path,'after',records);original=tx.path.read_bytes()
    if badge=='correct':
        assert tx.reconcile_purchase('scope','floor1:shop1',after)
        assert tx.data['pending'] is None
        assert tx.data['bought'][-1]['shelf_evidence']=='own_purchased_badge'
    else:
        with pytest.raises(ValueError):tx.reconcile_purchase('scope','floor1:shop1',after)
        assert tx.path.read_bytes()==original
