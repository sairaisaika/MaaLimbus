"""The native ``E.G.O Gift GET!`` acknowledgement: one input, no invented receipt.

A real shop purchase raises the notice over the shelf, so the shelf that proves the
coins is behind it and the run used to stop with ``shop_receipt_successor_not_proven``.
These tests pin the shape of the fix: the notice's own identity is proved from the
retained frame, the one acknowledgement is anchored *before* input, a restart can never
send it twice, and the purchase is still only receipted by the shelf that comes back
with the exact coin delta.
"""
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from maalimbus.shop_skill_vision import (GIFT_GET_CONFIRM_BOX, GIFT_GET_TITLE,
                                         GIFT_GET_TITLE_BOX, frame_overlay, read_overlay)
from maalimbus.shop_transaction import ShopTransaction
from maalimbus.storage import write_json

#: The one retained frame in this workspace that shows the notice, with the shelf of a
#: purchase behind it.  Nothing here writes to it.
LIVE_GET = ROOT / 'evidence/runtime/window-20261006-042640/frame-0066.json'


def json_safe(value):
    return json.loads(json.dumps(value, allow_nan=False))


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


def notice(rows, title=GIFT_GET_TITLE, title_box=GIFT_GET_TITLE_BOX,
           confirm='Confirm', confirm_box=GIFT_GET_CONFIRM_BOX):
    """The real notice's own two texts over whatever the shelf already printed."""
    rows = list(rows)
    if title is not None:
        rows.append(row(title, title_box))
    if confirm is not None:
        rows.append(row(confirm, confirm_box))
    return rows


def frame(tmp_path, label, rows, scene='SHOP', pixels=None):
    path = tmp_path / (label + '.json')
    image = (pixels or label).encode()
    path.with_suffix('.png').write_bytes(image)
    write_json(path, dict(scene=scene, size=[1920, 1080], ocr=rows,
                          image_sha256=hashlib.sha256(image).hexdigest()))
    return path


def started(tmp_path, names=('Oracle', 'Scalpel'), coins=100):
    before = frame(tmp_path, 'before', shelf(names, coins))
    tx = ShopTransaction(tmp_path / 'tx.json')
    tx.begin_visit('scope', 'floor1:shop1', before)
    return tx, before


def pending_purchase(tx, before):
    """Reserve the card intent and its purchase question, as the runner does."""
    tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 100, before)
    dialog = frame(Path(tx.path).parent, 'dialog', question(), 'SHOP_PURCHASE')
    assert tx.reserve_confirm('scope', 'floor1:shop1', dialog) == [1040, 760, 120, 34]
    return dialog


# --- the real notice -----------------------------------------------------------------

def test_the_retained_live_notice_is_read_as_the_notice_it_is():
    result = frame_overlay(LIVE_GET, require_scene='GIFT_GET')
    assert result['available'] is True and result['complete'] is True
    # The exact measured boxes of anchors.json id gift_get, not a guessed layout.
    assert result['title'] == 'E.G.O Gift GET!' and result['title_box'] == [828, 250, 258, 41]
    assert result['confirm'] == 'Confirm' and result['confirm_box'] == [922, 774, 136, 45]
    assert result['target'] == [922, 774, 136, 45]
    assert result['scene'] == 'GIFT_GET' and result['layout_known'] is True
    assert result['refused'] == [] and result['reason'] is None
    assert result['image_sha256_source'] == 'retained_png'
    assert result['declared_image_sha256'] == result['image_sha256']
    assert result['authorized'] is False and result['would_spend'] is False
    assert result['input_sent'] is False and result['game_controller'] is False
    assert json_safe(result) == result


def test_a_gift_get_without_the_notice_confirm_stays_unread():
    result = frame_overlay(LIVE_GET, require_scene='GIFT_GET')
    rows = [r for r in json.loads(LIVE_GET.read_text(encoding='utf-8'))['ocr']
            if r['text'].strip() != 'Confirm']
    partial = read_overlay(rows, (1920, 1080), scene='GIFT_GET', require_scene='GIFT_GET')
    assert partial['available'] is True and partial['complete'] is False
    assert partial['target'] is None and partial['reason'] == 'overlay_confirm_not_proven'


def test_the_notice_is_never_read_out_of_a_scene_that_is_not_the_notice():
    for scene in ('UNKNOWN', 'UNKNOWN_DIALOG', 'REWARD_CARD', None):
        result = read_overlay([], (1920, 1080), scene=scene, require_scene='GIFT_GET')
        assert result['available'] is False and result['target'] is None
        # The refusal names the scene the reader required, not a caller-supplied one.
        assert result['reason'] == 'overlay_scene_not_gift_get'
    # And a retained frame of any other scene reaches the same refusal.
    live = json.loads(LIVE_GET.read_text(encoding='utf-8'))
    other = read_overlay(live['ocr'], live['size'], scene='SHOP', require_scene='GIFT_GET')
    assert other['available'] is False and other['reason'] == 'overlay_scene_not_gift_get'


def test_the_locale_pattern_cannot_widen_what_the_notice_may_say():
    # A frame carrying the shelf's own labels is not the notice even when a pattern is
    # supplied for it: only the proved notice title counts.
    loose = read_overlay(notice(shelf(), title='E.G.O Gift', title_box=(828, 250, 258, 41)),
                         (1920, 1080), scene='GIFT_GET', require_scene='GIFT_GET',
                         title_pattern=r'.*')
    assert loose['available'] is False and loose['reason'] == 'overlay_title_differs_from_proved_notice'


def test_an_ambiguous_title_is_not_compressed_into_one_notice():
    rows = notice(shelf()) + [row(GIFT_GET_TITLE, (830, 254, 250, 38))]
    result = read_overlay(rows, (1920, 1080), scene='GIFT_GET', require_scene='GIFT_GET')
    assert result['available'] is False and result['reason'] == 'overlay_title_ambiguous'


def test_a_tampered_retained_notice_frame_is_refused():
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / 'frame-0066.json'
        copy.write_text(LIVE_GET.read_text(encoding='utf-8'), encoding='utf-8')
        copy.with_suffix('.png').write_bytes(b'not the retained pixels')
        with pytest.raises(ValueError, match='PNG hash differs'):
            frame_overlay(copy, require_scene='GIFT_GET')


# --- the anchored acknowledgement ----------------------------------------------------

def test_the_notice_is_acknowledged_once_and_proves_no_purchase(tmp_path):
    tx, before = started(tmp_path)
    pending_purchase(tx, before)
    get = frame(tmp_path, 'get', notice(shelf()), 'GIFT_GET')
    assert tx.reserve_overlay_acknowledgement('scope', 'floor1:shop1', get) == [922, 774, 136, 45]
    acknowledgement = tx.data['pending']['overlay_acknowledgement']
    assert acknowledgement['kind'] == 'ego_gift_get_notice'
    assert acknowledgement['title'] == GIFT_GET_TITLE
    assert acknowledgement['target'] == [922, 774, 136, 45]
    assert acknowledgement['frame']['png_sha256'] == hashlib.sha256(b'get').hexdigest()
    assert acknowledgement['refused'] == []
    # The notice is an input anchor, never a receipt: nothing is bought and the intent
    # stays unresolved until the shelf itself returns with the coin delta.
    assert tx.bought_names == [] and tx.data['pending'] is not None

    restarted = ShopTransaction(tx.path)
    assert restarted.data['pending']['stage'] == 'overlay_intent'
    assert len(restarted.data['visits']['floor1:shop1']['overlay_acknowledgements']) == 1
    # A restart cannot send it twice: the intent is already past the stage that
    # acknowledges a notice, and no second acknowledgement can claim the intent.
    with pytest.raises(ValueError, match='not confirmed yet'):
        restarted.reserve_overlay_acknowledgement('scope', 'floor1:shop1', get)
    with pytest.raises(ValueError, match='already reserved'):
        restarted.reserve_confirm('scope', 'floor1:shop1', get)
    assert restarted.data['pending'] is not None and restarted.bought_names == []

    after = frame(tmp_path, 'after', shelf(('Scalpel',), 80))
    assert restarted.reconcile_purchase('scope', 'floor1:shop1', after)
    bought = restarted.data['bought'][0]
    assert bought['name'] == 'Oracle' and bought['price'] == 20
    assert bought['overlay_acknowledgement']['kind'] == 'ego_gift_get_notice'
    assert restarted.data['pending'] is None
    assert json_safe(restarted.data) == restarted.data


@pytest.mark.parametrize('change', ['no_notice', 'unknown_scene', 'missing_confirm',
                                    'ambiguous_confirm', 'replayed', 'unconfirmed'])
def test_an_unread_or_unearned_notice_is_never_acknowledged(tmp_path, change):
    tx, before = started(tmp_path)
    if change != 'unconfirmed':
        pending_purchase(tx, before)
    scene, rows, pixels = 'GIFT_GET', notice(shelf()), None
    if change == 'no_notice': rows = shelf()
    if change == 'unknown_scene': scene = 'UNKNOWN'
    if change == 'missing_confirm':
        rows = notice(shelf(), confirm=None)
    if change == 'ambiguous_confirm':
        rows = notice(shelf()) + [row('Confirm', (926, 778, 130, 40))]
    if change == 'replayed': pixels = 'before'
    if change == 'unconfirmed':
        tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 100, before)
    path = frame(tmp_path, 'notice-' + change, rows, scene, pixels=pixels)
    original = tx.path.read_bytes()
    with pytest.raises(ValueError):
        tx.reserve_overlay_acknowledgement('scope', 'floor1:shop1', path)
    assert tx.path.read_bytes() == original
    pending = tx.data['pending']
    assert not (pending and pending.get('overlay_acknowledgement'))


def test_a_notice_whose_retained_pixels_changed_is_refused_on_the_retry(tmp_path):
    tx, before = started(tmp_path)
    pending_purchase(tx, before)
    get = frame(tmp_path, 'get', notice(shelf()), 'GIFT_GET')
    tx.reserve_overlay_acknowledgement('scope', 'floor1:shop1', get)
    get.with_suffix('.png').write_bytes(b'pixels replaced after the intent was anchored')
    restarted = ShopTransaction(tx.path)
    with pytest.raises(ValueError, match='PNG hash differs'):
        restarted.reserve_overlay_acknowledgement('scope', 'floor1:shop1', get)


def test_the_acknowledgement_never_clears_an_unknown_pending_action(tmp_path):
    tx, before = started(tmp_path)
    tx.reserve_purchase('scope', 'floor1:shop1', dict(name='Oracle', price=20), 100, before)
    get = frame(tmp_path, 'get', notice(shelf()), 'GIFT_GET')
    original = tx.path.read_bytes()
    # A notice seen before the purchase question was answered is not proof that the
    # question was answered, so the unknown pending action is preserved byte for byte.
    with pytest.raises(ValueError, match='not confirmed yet'):
        tx.reserve_overlay_acknowledgement('scope', 'floor1:shop1', get)
    assert tx.path.read_bytes() == original
    assert tx.data['pending']['stage'] == 'card_intent'
    assert tx.bought_names == []
