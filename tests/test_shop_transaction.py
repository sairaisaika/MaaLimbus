"""Offline durable-intent tests. Synthetic questions are not live-layout proof."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from maalimbus.shop_transaction import ShopTransaction
from maalimbus.shop_vision import matching_purchase_question
from maalimbus.storage import write_json
from maalimbus.vision import Text


def row(text, box, score=.99):
    return dict(text=text, box=list(box), score=score)


def shelf(names=('Oracle', 'Scalpel'), coins=100):
    rows = [row(str(coins), (850, 180, 80, 35)),
            row('Refresh', (1490, 160, 100, 35)), row('15', (1510, 210, 40, 30))]
    for index, name in enumerate(names):
        x = 930 + index * 230
        rows.extend([row('20', (x - 15, 460, 30, 30)),
                     row(name, (x - 80, 494, 160, 30))])
    return rows


def question(name='Oracle', price=20):
    return [row('Purchase "' + name + '" for ' + str(price) + '?', (730, 330, 450, 35)),
            row(name, (820, 410, 240, 35)), row(str(price), (890, 470, 50, 35)),
            row('Confirm', (1040, 760, 120, 34)), row('Cancel', (700, 760, 120, 34))]


def frame(tmp_path, label, rows, scene='SHOP', pixels=None):
    path = tmp_path / (label + '.json')
    image = (pixels or label).encode()
    path.with_suffix('.png').write_bytes(image)
    write_json(path, dict(scene=scene, size=[1920, 1080], ocr=rows,
                          image_sha256=hashlib.sha256(image).hexdigest()))
    return path


def setup(tmp_path):
    before = frame(tmp_path, 'before', shelf())
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor1:shop1', before)
    return tx, before


def reserve(tx, before):
    return tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 100, before)


def test_reservation_survives_restart_without_claiming_purchase(tmp_path):
    tx, before = setup(tmp_path)
    assert reserve(tx, before) == [870, 357, 120, 90]
    assert tx.bought_names == []
    restarted = ShopTransaction(tx.path)
    original = tx.path.read_bytes()
    with pytest.raises(ValueError, match='never repeat'):
        reserve(restarted, before)
    with pytest.raises(ValueError, match='never reset'):
        restarted.begin_visit('scope', 'newvisit', before)
    assert tx.path.read_bytes() == original


@pytest.mark.parametrize('change', ['price', 'name', 'currency', 'lowname', 'ambiguouscoins'])
def test_changed_or_incomplete_fresh_offer_refuses_before_write(tmp_path, change):
    tx, before = setup(tmp_path)
    rows = shelf()
    if change == 'price': rows[3]['text'] = '21'
    if change == 'name': rows[4]['text'] = 'Oracl'
    if change == 'currency': rows[0]['text'] = '99'
    if change == 'lowname': rows[4]['score'] = .899
    if change == 'ambiguouscoins': rows.append(row('101', (870, 215, 70, 25)))
    changed = frame(tmp_path, 'changed', rows)
    original = tx.path.read_bytes()
    with pytest.raises(ValueError): reserve(tx, changed)
    assert tx.path.read_bytes() == original


@pytest.mark.parametrize('change', ['missingprice', 'wrongname', 'wrongprice', 'lowquestion',
                                  'noquestion', 'duplicateconfirm', 'backgroundtitle'])
def test_generic_or_mismatched_question_never_confirms(tmp_path, change):
    tx, before = setup(tmp_path)
    reserve(tx, before)
    rows = question()
    if change == 'missingprice': rows[0]['text'] = 'Purchase "Oracle"?'; rows.pop(2)
    if change == 'wrongname': rows[0]['text'] = 'Purchase "Scalpel" for 20?'
    if change == 'wrongprice': rows[0]['text'] = 'Purchase "Oracle" for 21?'
    if change == 'lowquestion': rows[0]['score'] = .899
    if change == 'noquestion': rows.pop(0)
    if change == 'duplicateconfirm': rows.append(row('Confirm', (1190, 770, 120, 30)))
    if change == 'backgroundtitle': rows[0]['text'] = 'Purchase this E.G.O Gift?'
    path = frame(tmp_path, change, rows, 'SHOP_PURCHASE')
    original = tx.path.read_bytes()
    with pytest.raises(ValueError, match='not proven'): tx.reserve_confirm('scope', 'floor1:shop1', path)
    assert tx.path.read_bytes() == original


def test_exact_question_confirm_once_then_complete_delta(tmp_path):
    tx, before = setup(tmp_path)
    reserve(tx, before)
    dialog = frame(tmp_path, 'dialog', question(), 'SHOP_PURCHASE')
    assert tx.reserve_confirm('scope', 'floor1:shop1', dialog) == [1040, 760, 120, 34]
    assert tx.bought_names == []
    restarted = ShopTransaction(tx.path)
    with pytest.raises(ValueError): restarted.reserve_confirm('scope', 'floor1:shop1', dialog)
    after = frame(tmp_path, 'after', shelf(('Scalpel',), 80))
    assert restarted.reconcile_purchase('scope', 'floor1:shop1', after)
    assert restarted.bought_names == ['Oracle']
    assert restarted.data['pending'] is None
    again = frame(tmp_path, 'again', shelf(coins=80))
    with pytest.raises(ValueError, match='already receipted'):
        restarted.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 80, again)


@pytest.mark.parametrize('change', ['wrongdelta', 'present', 'incomplete', 'unknown', 'genericget'])
def test_receipt_needs_complete_independent_shelf_and_delta(tmp_path, change):
    tx, before = setup(tmp_path)
    reserve(tx, before)
    scene, rows = 'SHOP', shelf(('Scalpel',), 80)
    if change == 'wrongdelta': rows[0]['text'] = '79'
    if change == 'present': rows = shelf(coins=80)
    if change == 'incomplete': rows = shelf((), 80)
    if change == 'unknown': scene = 'UNKNOWN'
    if change == 'genericget': scene, rows = 'GIFT_ACK', [row('GET', (1000, 800, 100, 30))]
    path = frame(tmp_path, change, rows, scene)
    original = tx.path.read_bytes()
    with pytest.raises(ValueError): tx.reconcile_purchase('scope', 'floor1:shop1', path)
    assert tx.path.read_bytes() == original
    assert tx.bought_names == []


@pytest.mark.parametrize('changed', ['beforejson', 'beforepng', 'questionjson', 'questionpng'])
def test_changed_retained_proof_keeps_pending_bytes(tmp_path, changed):
    tx, before = setup(tmp_path)
    reserve(tx, before)
    dialog = frame(tmp_path, 'dialog', question(), 'SHOP_PURCHASE')
    tx.reserve_confirm('scope', 'floor1:shop1', dialog)
    target = before if changed.startswith('before') else dialog
    if changed.endswith('png'): target = target.with_suffix('.png')
    target.write_bytes(target.read_bytes() + b' ')
    after = frame(tmp_path, 'after', shelf(('Scalpel',), 80))
    original = tx.path.read_bytes()
    with pytest.raises(ValueError): tx.reconcile_purchase('scope', 'floor1:shop1', after)
    assert tx.path.read_bytes() == original


def test_stale_question_and_foreign_scope_never_write(tmp_path):
    tx, before = setup(tmp_path)
    reserve(tx, before)
    stale = frame(tmp_path, 'stale', question(), 'SHOP_PURCHASE', pixels='before')
    original = tx.path.read_bytes()
    with pytest.raises(ValueError, match='stale'): tx.reserve_confirm('scope', 'floor1:shop1', stale)
    with pytest.raises(ValueError, match='another'): tx.reserve_confirm('other', 'floor1:shop1', stale)
    assert tx.path.read_bytes() == original


def test_refresh_reservation_cap_and_unknown_survive_restart(tmp_path):
    tx, before = setup(tmp_path)
    assert tx.reserve_refresh('scope', 'floor1:shop1', 15, 100, 1, before) == [1490, 160, 100, 35]
    restarted = ShopTransaction(tx.path)
    assert restarted.refreshes_used('scope', 'floor1:shop1') == 1
    unknown = frame(tmp_path, 'unknown', [], 'UNKNOWN')
    original = tx.path.read_bytes()
    with pytest.raises(ValueError): restarted.close_visit('scope', 'floor1:shop1', unknown)
    with pytest.raises(ValueError): restarted.reserve_refresh('scope', 'floor1:shop1', 15, 100, 1, before)
    assert tx.path.read_bytes() == original
    after = frame(tmp_path, 'after', shelf(('Voodoo Doll', 'Scalpel'), 85))
    assert restarted.reconcile_refresh('scope', 'floor1:shop1', after)
    with pytest.raises(ValueError, match='limit'): restarted.reserve_refresh('scope', 'floor1:shop1', 15, 85, 1, after)
    bytes_before = tx.path.read_bytes()
    assert not restarted.begin_visit('scope', 'floor1:shop1', after)
    assert tx.path.read_bytes() == bytes_before


def test_only_new_verified_visit_resets_refresh_cap_not_bought_names(tmp_path):
    tx, before = setup(tmp_path)
    reserve(tx, before)
    after = frame(tmp_path, 'after', shelf(('Scalpel',), 80))
    tx.reconcile_purchase('scope', 'floor1:shop1', after)
    with pytest.raises(ValueError): tx.begin_visit('scope', 'floor2:shop1', after)
    map_frame = frame(tmp_path, 'map', [row('Exploring Floor 1', (100, 100, 400, 40))], 'MAP')
    tx.close_visit('scope', 'floor1:shop1', map_frame)
    new_shop = frame(tmp_path, 'newshop', shelf(coins=150))
    tx.begin_visit('scope', 'floor2:shop1', new_shop)
    assert tx.bought_names == ['Oracle']
    assert tx.refreshes_used('scope', 'floor2:shop1') == 0


@pytest.mark.parametrize('mutation', ['negativeprice', 'foreignpending', 'unknownkind', 'malformed',
                                    'emptyintent', 'missingquestion'])
def test_malformed_persisted_state_is_never_replaced(tmp_path, mutation):
    tx, before = setup(tmp_path)
    reserve(tx, before)
    data = copy.deepcopy(tx.data)
    if mutation == 'negativeprice': data['pending']['price'] = -1
    if mutation == 'foreignpending': data['pending']['scope'] = 'other'
    if mutation == 'unknownkind': data['pending']['kind'] = 'anything'
    if mutation == 'emptyintent': data['pending'] = {}
    if mutation == 'missingquestion': data['pending']['stage'] = 'confirm_intent'
    if mutation == 'malformed': data = []
    write_json(tx.path, data)
    original = tx.path.read_bytes()
    with pytest.raises(ValueError): ShopTransaction(tx.path)
    assert tx.path.read_bytes() == original


def test_full_named_sentence_has_no_fuzzy_title_match():
    rows = [Text(r['text'], tuple(r['box']), r['score']) for r in question()]
    rows = rows[3:] + [Text('Purchase "Oracle" for 20?', (700, 430, 500, 40), .99)]
    assert matching_purchase_question(rows, 'Oracle', 20) == [1040, 760, 120, 34]
    assert matching_purchase_question(rows, 'Oracl', 20) is None
    assert matching_purchase_question(rows, 'Oracle', 21) is None


def test_generic_question_cannot_borrow_background_shelf_title_and_price():
    rows = [Text(r['text'], tuple(r['box']), r['score']) for r in question()]
    rows[0] = Text('Purchase this E.G.O Gift?', rows[0].box, .99)
    assert matching_purchase_question(rows, 'Oracle', 20) is None
