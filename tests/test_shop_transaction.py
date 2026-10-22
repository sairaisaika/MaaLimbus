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


def test_a_reservation_the_modal_never_asked_about_is_retired(tmp_path):
    # Live 21:24:38: a resumed 159-coin reservation met a dialog whose own badge asked
    # 390.  The modal's Cancel answers it and the stale intent is dropped with it --
    # nothing is credited as bought, and the shelf can be read again next frame
    # instead of every later purchase being refused as 'already reserved'.
    tx, before = setup(tmp_path)
    reserve(tx, before)
    assert tx.retire_pending('scope', 'floor1:shop1', 'the_modal_asks_another_price') is True
    assert tx.data['pending'] is None
    assert tx.bought_names == []
    assert tx.data['visits']['floor1:shop1']['retired'] == [
        dict(name='Oracle', price=20, why='the_modal_asks_another_price')]
    restarted = ShopTransaction(tx.path)
    with pytest.raises(ValueError, match='No pending shop action'):
        restarted.retire_pending('scope', 'floor1:shop1')
    assert tx.path.read_bytes() == restarted.path.read_bytes()


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


# The 12:39 live run reserved its second refresh against frame-0064 and then
# refused frame-0065.  Both frames are retained verbatim, and the run's stored
# pending shelf held four rows where the successor read six -- so this pair is
# the regression itself, not a reconstruction of it.
LIVE_BEFORE = ROOT / 'evidence/runtime/pi-20261012-123906/frame-0064.json'
LIVE_AFTER = ROOT / 'evidence/runtime/pi-20261012-123906/frame-0065.json'


def test_an_intent_whose_click_left_the_question_behind_is_dropped_unspent(tmp_path):
    """Live window-20261012-210547: the cap's click on the shelf offer "Replace Don
    Qubote's Sil" opened the skill-replacement chooser, so the shop's purchase question
    never appeared.  The shelf that follows still prints that card at its own price,
    without its Purchased badge, and the visit's currency is exactly what it was: nothing
    was bought, so the intent is dropped unspent instead of stopping the run forever.
    """
    tx, before = setup(tmp_path)
    assert reserve(tx, before) == [870, 357, 120, 90]
    unchanged = frame(tmp_path, 'unchanged', shelf())
    assert tx.reconcile_purchase('scope', 'floor1:shop1', unchanged) is True
    assert tx.data['pending'] is None and tx.data['bought'] == []
    dropped = tx.data['unspent_intents'][0]
    assert dropped['name'] == 'Oracle' and dropped['price'] == 20
    assert dropped['stage'] == 'card_intent'
    assert dropped['shelf_evidence'] == 'unchanged_shelf_and_untouched_currency'
    assert 'png_sha256' in dropped['successor']


@pytest.mark.parametrize('rows,coins', [
    (shelf(coins=120), 120),          # the currency moved: the delta rule owns this case
    (shelf(names=('Scalpel',)), 100),  # the card is gone: disappearance owns it too
])
def test_an_unspent_intent_needs_the_unchanged_shelf_and_currency(tmp_path, rows, coins):
    tx, before = setup(tmp_path)
    assert reserve(tx, before) == [870, 357, 120, 90]
    successor = frame(tmp_path, 'successor', rows)
    with pytest.raises(ValueError, match='Exact shop purchase currency delta not proven'):
        tx.reconcile_purchase('scope', 'floor1:shop1', successor)
    assert tx.data['pending'] is not None and not tx.data.get('unspent_intents')


def test_the_live_refresh_pair_reserves_and_reconciles(tmp_path):
    if not LIVE_BEFORE.exists() or not LIVE_AFTER.exists():
        pytest.skip('retained live shop evidence is not present')
    tx = ShopTransaction(tmp_path / 'tx.json')
    assert tx.begin_visit('scope', 'floor2:shop1', LIVE_BEFORE)
    click = tx.reserve_refresh('scope', 'floor2:shop1', 30, 1647, 2, LIVE_BEFORE)
    assert len(click) == 4 and all(type(value) is int for value in click)
    # The whole six-slot shelf is what the reservation retains; the run that
    # stored four rows is why the successor could never match.
    assert len(tx.data['pending']['shelf']) == 6
    assert tx.reconcile_refresh('scope', 'floor2:shop1', LIVE_AFTER) is True
    assert tx.refreshes_used('scope', 'floor2:shop1') == 1
    assert tx.data['pending'] is None


def test_a_pending_written_by_a_sparser_reader_still_reconciles(tmp_path):
    """The stored shelf is a reader's opinion, not the shelf.

    The 12:39 run's own pending holds four rows because the build that reserved it
    dropped two prices at its score cut.  The retained frame did not change, so the
    baseline is re-read: the successor shelf must be complete against the frame, and
    an intent recorded by an older reader must not become permanently unreconcilable.
    """
    if not LIVE_BEFORE.exists() or not LIVE_AFTER.exists():
        pytest.skip('retained live shop evidence is not present')
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor2:shop1', LIVE_BEFORE)
    tx.reserve_refresh('scope', 'floor2:shop1', 30, 1647, 2, LIVE_BEFORE)
    stale = [dict(name='Melted Paraffin', price=150, click=[0, 0, 1, 1]),
             dict(name='Thorny Path', price=160, click=[0, 0, 1, 1]),
             dict(name='Resolution', price=207, click=[0, 0, 1, 1]),
             dict(name='UPS System', price=156, click=[0, 0, 1, 1])]
    data = copy.deepcopy(tx.data)
    data['pending']['shelf'] = stale
    tx._save(data)
    assert len(tx.data['pending']['shelf']) == 4
    assert tx.reconcile_refresh('scope', 'floor2:shop1', LIVE_AFTER) is True
    assert tx.data['pending'] is None


def test_a_sparse_successor_shelf_is_still_refused(tmp_path):
    """Re-reading the baseline must not turn the completeness check off.

    The baseline is now the frame's own reading, so the bar is the whole shelf:
    a successor that reads one offer where the frame holds two is refused even
    though its coin delta is exact and its fingerprint differs.
    """
    tx, before = setup(tmp_path)
    tx.reserve_refresh('scope', 'floor1:shop1', 15, 100, 1, before)
    sparse = frame(tmp_path, 'sparse', shelf(('Voodoo Doll',), 85))
    with pytest.raises(ValueError, match='complete changed shelf not proven'):
        tx.reconcile_refresh('scope', 'floor1:shop1', sparse)
    assert tx.data['pending'] is not None


def test_the_cards_own_purchased_badge_is_the_receipt_for_its_own_card(tmp_path):
    """A badge settles the purchase even when another slot of the shelf reads short.

    Live frame ``window-20261012-203743/frame-0149`` kept the bought card under its
    own ``Purchased`` badge while its neighbour's badge read .763, below the floor
    that prices a card.  The complete-shelf comparison then refused a purchase the
    page had already completed; the badge plus the exact coin delta is the receipt.
    """
    tx, before = setup(tmp_path)
    reserve(tx, before)
    tx.reserve_confirm('scope', 'floor1:shop1',
                       frame(tmp_path, 'dialog', question(), 'SHOP_PURCHASE'))
    after = frame(tmp_path, 'after',
                  shelf(('Oracle',), 80) + [row('Purchased', (870, 320, 120, 40))])
    assert tx.reconcile_purchase('scope', 'floor1:shop1', after) is True
    assert tx.data['pending'] is None
    assert tx.data['bought'][-1]['name'] == 'Oracle'
    assert tx.data['bought'][-1]['shelf_evidence'] == 'own_purchased_badge'


def test_the_badge_path_records_a_card_the_shelf_never_held(tmp_path):
    """The receipt is the bought card's badge plus the delta, not the neighbours.

    ``Wobbling Keg`` was not on this session's shelf at all, so the successor is a
    different shop instance.  The account paid 20 for ``Oracle``, whose own Purchased
    badge is present, and that is the receipt; the stranger is recorded as a note.
    """
    tx, before = setup(tmp_path)
    reserve(tx, before)
    tx.reserve_confirm('scope', 'floor1:shop1',
                       frame(tmp_path, 'dialog', question(), 'SHOP_PURCHASE'))
    after = frame(tmp_path, 'after',
                  shelf(('Oracle', 'Wobbling Keg'), 80)
                  + [row('Purchased', (870, 320, 120, 40))])
    assert tx.reconcile_purchase('scope', 'floor1:shop1', after) is True
    assert tx.bought_names == ['Oracle']
    assert tx.data['bought'][-1]['successor_note']['offers'] == ['Wobbling Keg']


def test_a_title_differing_only_in_the_typefaces_confusable_glyph_is_the_same_card(tmp_path):
    """The shelf's own typeface is what spells the card two ways.

    Live ``window-20261012-221212`` reserved "Today's Expression", the counter went
    2993 -> 2804 for its 189, and the successor printed that same slot under its own
    Purchased badge as "Today's Expresslon".  The exact-title match found no bought
    card, so the whole-shelf comparison refused a purchase the page had completed.
    """
    before = frame(tmp_path, 'before', shelf(("Today's Expression", 'Scalpel')))
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor1:shop1', before)
    tx.reserve_purchase('scope', 'floor1:shop1',
                        dict(name="Today's Expression", price=20), 100, before)
    tx.reserve_confirm('scope', 'floor1:shop1',
                       frame(tmp_path, 'dialog', question("Today's Expression", 20),
                             'SHOP_PURCHASE'))
    after = frame(tmp_path, 'after', shelf(("Today's Expresslon",), 80)
                  + [row('Purchased', (870, 320, 120, 40))])
    assert tx.reconcile_purchase('scope', 'floor1:shop1', after) is True
    assert tx.bought_names == ["Today's Expression"]
    assert tx.data['bought'][-1]['shelf_evidence'] == 'own_purchased_badge'
    assert tx.data['pending'] is None


def test_a_condensed_ligature_reads_as_the_same_slot(tmp_path):
    """A condensed ``rn`` folds into ``m``, so the slot must not become a new card.

    Live ``pi-20261014-080122`` reserved a purchase on a six-slot shelf whose own
    frames read its 160-coin slot as "Thomy Path"; the returning shelf printed that
    same slot, price and card as "Thorny Path", its catalogue name.  The badge path
    then refused the purchase as a successor showing an offer "the shelf never held"
    and the run stopped at floor 3.
    """
    before = frame(tmp_path, 'before', shelf(('Oracle', 'Thomy Path')))
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor1:shop1', before)
    tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 100, before)
    tx.reserve_confirm('scope', 'floor1:shop1',
                       frame(tmp_path, 'dialog', question(), 'SHOP_PURCHASE'))
    after = frame(tmp_path, 'after', shelf(('Oracle', 'Thorny Path'), 80)
                  + [row('Purchased', (870, 320, 120, 40))])
    assert tx.reconcile_purchase('scope', 'floor1:shop1', after) is True
    assert tx.bought_names == ['Oracle']
    assert tx.data['pending'] is None


def test_a_neighbour_this_session_never_saw_is_a_note_not_a_stop(tmp_path):
    """The bought card's own badge plus the exact delta is the receipt.

    ``Thorny Rd`` is not the ``Thorny Path`` the shelf held: the successor here is a
    different shop instance (a shelf that re-rolled between the two sessions of a
    resumed run, live run ``packaged-mirror-20261022-012400``).  The account still paid
    exactly 20 for exactly ``Oracle`` and that card carries its own Purchased badge, so
    what the neighbour changed to says nothing about the receipt -- it is recorded.
    """
    before = frame(tmp_path, 'before', shelf(('Oracle', 'Thorny Path')))
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor1:shop1', before)
    tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 100, before)
    tx.reserve_confirm('scope', 'floor1:shop1',
                       frame(tmp_path, 'dialog', question(), 'SHOP_PURCHASE'))
    after = frame(tmp_path, 'after', shelf(('Oracle', 'Thorny Rd'), 80)
                  + [row('Purchased', (870, 320, 120, 40))])
    assert tx.reconcile_purchase('scope', 'floor1:shop1', after) is True
    assert tx.bought_names == ['Oracle']
    assert tx.data['pending'] is None
    note = tx.data['bought'][-1]['successor_note']
    assert note['reason'] == ('the_successor_shelf_holds_offers_this_session_never_saw')
    assert note['offers'] == ['Thorny Rd']
    assert tx.data['bought'][-1]['shelf_evidence'] == 'own_purchased_badge'


def test_a_space_the_reader_dropped_still_names_the_same_slot(tmp_path):
    """A word gap the reader lost folds away, so the slot is not a new card.

    Live ``pi-20261014-082326`` reserved a card from a shelf whose own frame-0002 read
    the 144-coin slot as "Crownof Roses"; the returning shelf (frame-0008) printed the
    catalogue spacing "Crown of Roses", the two keys differed by one blank, and the run
    stopped after 3 inputs as a successor showing an offer "the shelf never held".
    """
    before = frame(tmp_path, 'before', shelf(('Oracle', 'Crownof Roses')))
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor1:shop1', before)
    tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 100, before)
    tx.reserve_confirm('scope', 'floor1:shop1',
                       frame(tmp_path, 'dialog', question(), 'SHOP_PURCHASE'))
    after = frame(tmp_path, 'after', shelf(('Oracle', 'Crown of Roses'), 80)
                  + [row('Purchased', (870, 320, 120, 40))])
    assert tx.reconcile_purchase('scope', 'floor1:shop1', after) is True
    assert tx.bought_names == ['Oracle']
    assert tx.data['pending'] is None


def test_the_space_fold_is_not_a_licence_to_shorten_a_title(tmp_path):
    """A lost blank folds away; a lost letter still refuses."""
    before = frame(tmp_path, 'before', shelf(('Oracle', 'Crown of Roses')))
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor1:shop1', before)
    tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 100, before)
    tx.reserve_confirm('scope', 'floor1:shop1',
                       frame(tmp_path, 'dialog', question(), 'SHOP_PURCHASE'))
    after = frame(tmp_path, 'after', shelf(('Oracle', 'Crown of Rose'), 80)
                  + [row('Purchased', (870, 320, 120, 40))])
    assert tx.reconcile_purchase('scope', 'floor1:shop1', after) is True
    assert tx.bought_names == ['Oracle']


def test_a_decision_context_keeps_bought_names_and_never_their_records(tmp_path):
    """A record embeds its own context, so the store keeps names.

    Live ``pi-20261014-082856`` could not start: the state had reached 2,464,332 bytes
    because each purchase's context embedded the whole earlier records.
    """
    before = frame(tmp_path, 'before', shelf(('Oracle', 'Thorny Path')))
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor1:shop1', before)
    record = dict(name='Emerald Elytra', price=160,
                  decision_context=dict(owned_bought=[dict(name='Stone Tomb', price=5)]))
    tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 100, before,
                        decision_context=dict(keywords=['Bleed'],
                                              owned_bought=[dict(name='Emerald Elytra', price=160),
                                                            'Stone Tomb'],
                                              offer=record))
    context = tx.data['pending']['decision_context']
    assert context['owned_bought'] == ['Emerald Elytra', 'Stone Tomb']
    assert context['keywords'] == ['Bleed']


def test_a_decision_context_of_an_unknown_shape_is_refused(tmp_path):
    before = frame(tmp_path, 'before', shelf(('Oracle', 'Thorny Path')))
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor1:shop1', before)
    with pytest.raises(ValueError, match='Invalid shop decision context'):
        tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 100, before,
                            decision_context=dict(owned_bought=[7]))
    assert tx.data['pending'] is None


def test_the_confusable_fold_never_adopts_a_card_with_a_different_glyph(tmp_path):
    """The fold covers the typeface's own pairs, not titles in general.

    The exact coin delta still receipts the purchase, but the *identity* of what was
    bought comes from the reservation, never from a successor slot whose name merely
    looks similar, so the successor can neither adopt nor rename the card.

    Live: run ``pi-20261015-215812`` resumed the reservation an earlier run left behind,
    paid its 390 (1809 -> 1419), and its successor shelf kept printing the truncated
    title at the same price with no badge; that mismatch is now recorded instead of
    ending the run.
    """
    tx, before = setup(tmp_path)
    reserve(tx, before)
    tx.reserve_confirm('scope', 'floor1:shop1',
                       frame(tmp_path, 'dialog', question(), 'SHOP_PURCHASE'))
    after = frame(tmp_path, 'after', shelf(('Orach',), 80)
                  + [row('Purchased', (870, 320, 120, 40))])
    assert tx.reconcile_purchase('scope', 'floor1:shop1', after) is True
    bought = tx.data['bought'][-1]
    assert bought['name'] == 'Oracle' and bought['price'] == 20
    assert bought['shelf_evidence'] == 'exact_currency_delta'
    assert bought['successor_note']['reason'] == (
        'the_successor_shelf_could_not_corroborate_the_exact_currency_delta')
    assert tx.bought_names == ['Oracle']
    assert tx.data['pending'] is None


LIVE_CONFUSABLE_BEFORE = ROOT / 'evidence/runtime/window-20261012-221212/frame-0002.json'
LIVE_CONFUSABLE_QUESTION = ROOT / 'evidence/runtime/window-20261012-221212/frame-0004.json'
LIVE_CONFUSABLE_AFTER = ROOT / 'evidence/runtime/window-20261012-221212/frame-0008.json'


def test_the_live_confusable_successor_is_receipted(tmp_path):
    """The round trip that exposed the fold, replayed from its own three frames."""
    if not all(path.exists() for path in (LIVE_CONFUSABLE_BEFORE,
                                          LIVE_CONFUSABLE_QUESTION,
                                          LIVE_CONFUSABLE_AFTER)):
        pytest.skip('retained live shop evidence is not present')
    tx = ShopTransaction(tmp_path / 'tx.json')
    assert tx.begin_visit('scope', 'floor4:shop1', LIVE_CONFUSABLE_BEFORE)
    assert tx.reserve_purchase('scope', 'floor4:shop1',
                               dict(name="Today's Expression", price=189), 2993,
                               LIVE_CONFUSABLE_BEFORE)
    assert tx.data['pending']['shelf'][1]['name'] == "Today's Expression"
    assert len(tx.reserve_confirm('scope', 'floor4:shop1', LIVE_CONFUSABLE_QUESTION)) == 4
    assert tx.reconcile_purchase('scope', 'floor4:shop1', LIVE_CONFUSABLE_AFTER) is True
    bought = tx.data['bought'][-1]
    assert bought['name'] == "Today's Expression" and bought['price'] == 189
    assert bought['shelf_evidence'] == 'own_purchased_badge'
    assert tx.data['pending'] is None


def test_a_neighbouring_slot_read_with_one_glyph_of_noise_is_still_the_same_page(tmp_path):
    """The page-identity check counts differing glyphs instead of listing them.

    Live ``pi-20261016-011659`` started, found the reservation an earlier run had left
    behind, read the successor shelf as "Vaodoo Doll" where its own baseline had read
    "Voodoo Doll" -- same slot, same 149, same visit -- and stopped at zero inputs.  The
    bought card's own badge plus the exact delta is the receipt; a neighbouring row read
    one position differently at the same price is the same page, not a different one.
    """
    before = frame(tmp_path, 'before', shelf(('Voodoo Doll', 'Scalpel')))
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor1:shop1', before)
    tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Scalpel', price=20), 100, before)
    tx.reserve_confirm('scope', 'floor1:shop1',
                       frame(tmp_path, 'dialog', question('Scalpel'), 'SHOP_PURCHASE'))
    after = frame(tmp_path, 'after', shelf(('Vaodoo Doll', 'Scalpel'), 80)
                  + [row('Purchased', (1100, 320, 120, 40))])
    assert tx.reconcile_purchase('scope', 'floor1:shop1', after) is True
    bought = tx.data['bought'][-1]
    assert bought['name'] == 'Scalpel' and bought['price'] == 20
    assert bought['shelf_evidence'] == 'own_purchased_badge'
    assert tx.data['pending'] is None


def test_one_glyph_of_noise_is_not_a_licence_to_shorten_or_repricing(tmp_path):
    """The tolerance is one position long at the same price, so a different card stays refused."""
    tx, before = setup(tmp_path)
    reserve(tx, before)
    tx.reserve_confirm('scope', 'floor1:shop1',
                       frame(tmp_path, 'dialog', question(), 'SHOP_PURCHASE'))
    after = frame(tmp_path, 'after', shelf(('Oracle', 'Wobbling Keg'), 80)
                  + [row('Purchased', (870, 320, 120, 40))])
    assert tx.reconcile_purchase('scope', 'floor1:shop1', after) is True
    note = tx.data['bought'][-1]['successor_note']
    assert note['offers'] == ['Wobbling Keg']


LIVE_RESUMED_BEFORE = ROOT / 'dist/MaaLimbus/evidence/runtime/pi-20261015-214921/frame-0002.json'
LIVE_RESUMED_QUESTION = ROOT / 'dist/MaaLimbus/evidence/runtime/pi-20261015-215812/frame-0002.json'
LIVE_RESUMED_AFTER = ROOT / 'dist/MaaLimbus/evidence/runtime/pi-20261016-011659/frame-0002.json'


def test_the_live_resumed_purchase_across_runs_is_receipted(tmp_path):
    """The round trip that exposed the check, replayed from its own three frames.

    A reservation one run left behind is reconciled by the next: 1809 -> 1419 for its 390,
    the card still under its own Purchased badge, and a neighbouring slot the successor
    read one glyph differently ("Vaodoo Doll" for "Voodoo Doll") at the same 149.
    """
    if not all(path.exists() for path in (LIVE_RESUMED_BEFORE, LIVE_RESUMED_QUESTION,
                                          LIVE_RESUMED_AFTER)):
        pytest.skip('retained live shop evidence is not present')
    tx = ShopTransaction(tmp_path / 'tx.json')
    assert tx.begin_visit('scope', 'floor4:shop1', LIVE_RESUMED_BEFORE)
    assert tx.reserve_purchase('scope', 'floor4:shop1',
                               dict(name='Clear Mirror, Calm Water', price=390), 1809,
                               LIVE_RESUMED_BEFORE)
    assert tx.reserve_confirm('scope', 'floor4:shop1', LIVE_RESUMED_QUESTION)
    assert tx.reconcile_purchase('scope', 'floor4:shop1', LIVE_RESUMED_AFTER) is True
    bought = tx.data['bought'][-1]
    assert bought['name'] == 'Clear Mirror, Calm Water' and bought['price'] == 390
    assert bought['shelf_evidence'] == 'own_purchased_badge'
    assert tx.data['pending'] is None

