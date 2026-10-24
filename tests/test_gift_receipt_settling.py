"""Retained Select/CONNECTING/GET sequence, driven without a controller."""
import json
import sys
from pathlib import Path

import cv2
import pytest

from maalimbus.floor_gifts import observe
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.runner import (FakeDevice, FrameObserver, MirrorRunner, events,
                              unselected_reward_successor)
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.storage import ProfileStore, RunStore
from maalimbus.vision import Text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'agent'))
from recognition import Journal

BEFORE = ROOT/'evidence/runtime/window-20261008-102111/frame-0435.json'
SELECTED = ROOT/'evidence/runtime/window-20261008-110526/frame-0001.json'
CONNECTING = SELECTED.with_name('frame-0002.json')
GET = ROOT/'evidence/runtime/window-20261008-110924/frame-0001.json'
#: Live GUI run pi-20261014-072228 pressed 'Select 2/2' for 'Prejudice' and
#: 'Uncapped Defibrilator'; the device answered on its own notice page with
#: 'Dark Vestige' -- a name from neither the pick page nor the selection.
LIVE_NOTICE = ROOT/'evidence/runtime/gui-20261014-072228/frame-0254.json'


def offer(frame):
    data = json.loads(frame.read_text())
    return observe([Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']],
                   data['size'], GiftCatalog(ROOT/'assets/resource/base'),
                   image=cv2.imread(str(frame.with_suffix('.png'))),
                   select_box=(1620, 851, 100, 36))


@pytest.mark.parametrize('successor', [GET, CONNECTING])
def test_select_waits_past_changed_offer_but_never_retries(tmp_path, successor):
    teams = (Team(2, frozenset({'Charge', 'Tremor'})),)
    ProfileStore(tmp_path/'user-team-profiles.json').save(teams)
    store = RunStore(tmp_path/'ledger.json', teams)
    scope = store.start()
    frames = [SELECTED, CONNECTING, successor]
    if successor == CONNECTING:
        frames.append(CONNECTING)
    device = FakeDevice([cv2.imread(str(f.with_suffix('.png'))) for f in frames])
    runner = MirrorRunner(device, settings={'rounds': 2, 'interval': 0},
                          store=store, run_id=scope, directory=tmp_path,
                          observer=FrameObserver(tmp_path, [str(f) for f in frames]))
    tx = runner.floor_gift_transaction
    offers, count = offer(BEFORE)
    tx.prepare(scope, offers, count, BEFORE)
    tx.intent('Perversion', count, BEFORE)
    offers, count = offer(SELECTED)
    tx.observe_pick(offers, count, SELECTED)

    runner.step()
    result = runner.artifacts['steps'][-1]
    assert len(device.clicks) == 1
    assert device.swipes == [] and device.keys == []
    assert len(list(tmp_path.glob('frame-*.json'))) == 3
    assert tx.data['pending']['kind'] == 'commit'
    assert tx.data['receipts'] == [] and not tx.data['completed']
    if successor == GET:
        assert result['page_after'] == 'GIFT_GET' and result['passed']
    else:
        assert result['reason'] == 'floor_gift_commit_receipt_not_proven'
        assert result['passed'] is False
        runner.step()
        assert len(device.clicks) == 1  # Unknown pending cannot re-submit Select.


REWARD = ROOT/'evidence/runtime/window-20261008-111130/frame-0002.json'


@pytest.mark.parametrize('missing', ['Select Encounter Reward Card', 'Confirm', 'Cancel', 'Selectable', '0/1'])
def test_reward_successor_requires_every_independent_anchor(missing):
    data = json.loads(REWARD.read_text())
    assert unselected_reward_successor(data)
    data['ocr'] = [r for r in data['ocr'] if missing not in r['text']]
    assert unselected_reward_successor(data) is None


def merged_counter_reward():
    """The retained reward page with the live OCR shape: ``Selectable 0/1`` whole."""
    data = json.loads(REWARD.read_text())
    merged, kept = None, []
    for r in data['ocr']:
        text = (r['text'] or '').strip()
        if text == 'Selectable':
            merged = dict(r, text='Selectable 0/1', box=[1326, 176, 214, 38])
            kept.append(merged)
        elif text == '0/1':
            continue
        else:
            kept.append(r)
    assert merged is not None
    data['ocr'] = kept
    return data, merged


def test_reward_successor_survives_the_counter_riding_the_selectable_line():
    """The live OCR keeps ``Selectable 0/1`` whole; the anchor must still fire.

    This retained frame splits the two tokens, so it proved the successor rule
    while the real page did not: a run clearing its gift notice onto a reward
    page stopped on ``floor_gift_receipt_successor_not_proven`` because an
    exact-match ``'Selectable' in texts`` never saw ``Selectable 0/1``.
    """
    data, merged = merged_counter_reward()
    assert unselected_reward_successor(data) == {'count': {'chosen': 0, 'required': 1},
                                                 'title': 'Select Encounter Reward Card'}
    data['ocr'] = [r for r in data['ocr'] if r is not merged]
    assert unselected_reward_successor(data) is None


def test_a_named_gift_receipt_settles_on_the_merged_counter_reward_page(tmp_path):
    """The page that stopped the live run settles the receipt once read as it prints."""
    frame = tmp_path/'frame-0178.json'
    data, _ = merged_counter_reward()
    frame.write_text(json.dumps(data))
    tx = FloorGiftTransaction(tmp_path/'tx.json')
    offers, count = offer(BEFORE)
    tx.prepare('scope', offers, count, BEFORE)
    tx.intent('Perversion', count, BEFORE)
    offers, count = offer(SELECTED)
    tx.observe_pick(offers, count, SELECTED)
    tx.commit(SELECTED)
    tx.receipt_intent('Perversion', GET)
    tx.observe_receipt('REWARD_CARD', None, frame,
                       next_reward_offer=unselected_reward_successor(data))
    assert tx.data['completed'] and tx.data['pending'] is None
    assert tx.data['next_reward_offer']['count'] == {'chosen': 0, 'required': 1}


def test_named_gift_receipt_can_finish_at_unselected_encounter_reward(tmp_path):
    tx = FloorGiftTransaction(tmp_path/'tx.json')
    offers, count = offer(BEFORE)
    tx.prepare('scope', offers, count, BEFORE)
    tx.intent('Perversion', count, BEFORE)
    offers, count = offer(SELECTED)
    tx.observe_pick(offers, count, SELECTED)
    tx.commit(SELECTED)
    tx.receipt_intent('Perversion', GET)
    with pytest.raises(ValueError):
        tx.observe_receipt('REWARD_CARD', None, REWARD)
    proof = unselected_reward_successor(json.loads(REWARD.read_text()))
    tx.observe_receipt('REWARD_CARD', None, REWARD, next_reward_offer=proof)
    assert tx.data['completed'] and tx.data['pending'] is None
    assert tx.data['receipts'][0]['title'] == 'Perversion'
    with pytest.raises(ValueError):
        tx.receipt_intent('Perversion', GET)


def test_runner_recovers_a_receipt_whose_successor_is_the_reward_page(tmp_path):
    """Recovery must honour the successor rule the settling path already honours.

    Live run ``pi-20261012-151818`` cleared the gift notice onto the encounter
    reward page with ``Selectable 0/1`` whole. The receipt guard accepted that page
    while the run held the frame, but re-reading the retained notice called the
    transaction's own settling rule with no successor at all, so the receipt stayed
    pending on every later step and the run stopped. Both paths read the page
    through one rule now, so the retained notice books and the run continues.
    """
    teams = (Team(2, frozenset({'Charge', 'Tremor'})),)
    ProfileStore(tmp_path/'user-team-profiles.json').save(teams)
    store = RunStore(tmp_path/'ledger.json', teams)
    scope = store.start()
    evidence = tmp_path/'runtime'/'pi-test'
    # The booked notice has to live under the evidence root: retained_notice_name
    # trusts a frame only inside the run's own tree.
    retained = tmp_path/'runtime'/'retained'
    retained.mkdir(parents=True)
    for suffix in ('.json', '.png'):
        (retained/f'frame-0001{suffix}').write_bytes(GET.with_suffix(suffix).read_bytes())
    reward, _ = merged_counter_reward()
    page = tmp_path/'successor'
    page.mkdir()
    (page/'frame-0002.json').write_text(json.dumps(reward))
    (page/'frame-0002.png').write_bytes(REWARD.with_suffix('.png').read_bytes())

    device = FakeDevice([cv2.imread(str(REWARD.with_suffix('.png')))]*3)
    runner = MirrorRunner(device, settings={'rounds': 2, 'interval': 0}, store=store,
                          run_id=scope, directory=evidence, journal=Journal(evidence),
                          observer=FrameObserver(evidence, [str(page/'frame-0002.png')]*6))
    tx = runner.floor_gift_transaction
    offers, count = offer(BEFORE)
    tx.prepare(scope, offers, count, BEFORE)
    tx.intent('Perversion', count, BEFORE)
    offers, count = offer(SELECTED)
    tx.observe_pick(offers, count, SELECTED)
    tx.commit(SELECTED)
    tx.receipt_intent('Perversion', retained/'frame-0001.json')

    runner.step()

    assert tx.data['completed'] is True and tx.data['pending'] is None
    recovered = events(evidence, 'floor_gift_receipt_recovered')
    assert len(recovered) == 1
    assert recovered[0]['title'] == 'Perversion'
    # The booking rests on the notice's own hash-checked frame.  ``printed`` only
    # carries whatever the loose middle-band reader saw here -- the reward page
    # prints '2~3 E.G.O Gift' straight into that band -- so it is not the proof.
    assert recovered[0]['before'] == str(retained/'frame-0001.json')
    assert events(evidence, 'floor_gift_receipt_unknown_repeated_or_pending') == []


def test_runner_still_refuses_a_successor_the_page_does_not_prove(tmp_path):
    """Widening the page set is not a weaker rule: an unproven page still stops.

    The same reward frame with its anchors removed proves nothing, so the retained
    notice must not be booked and the transaction must stay pending.
    """
    teams = (Team(2, frozenset({'Charge', 'Tremor'})),)
    ProfileStore(tmp_path/'user-team-profiles.json').save(teams)
    store = RunStore(tmp_path/'ledger.json', teams)
    scope = store.start()
    evidence = tmp_path/'runtime'/'pi-test'
    retained = tmp_path/'runtime'/'retained'
    retained.mkdir(parents=True)
    for suffix in ('.json', '.png'):
        (retained/f'frame-0001{suffix}').write_bytes(GET.with_suffix(suffix).read_bytes())
    stripped = json.loads(REWARD.read_text())
    stripped['ocr'] = [r for r in stripped['ocr']
                       if 'Select Encounter Reward Card' not in (r['text'] or '')]
    page = tmp_path/'successor'
    page.mkdir()
    (page/'frame-0002.json').write_text(json.dumps(stripped))
    (page/'frame-0002.png').write_bytes(REWARD.with_suffix('.png').read_bytes())

    device = FakeDevice([cv2.imread(str(REWARD.with_suffix('.png')))]*3)
    runner = MirrorRunner(device, settings={'rounds': 2, 'interval': 0}, store=store,
                          run_id=scope, directory=evidence, journal=Journal(evidence),
                          observer=FrameObserver(evidence, [str(page/'frame-0002.png')]*3))
    tx = runner.floor_gift_transaction
    offers, count = offer(BEFORE)
    tx.prepare(scope, offers, count, BEFORE)
    tx.intent('Perversion', count, BEFORE)
    offers, count = offer(SELECTED)
    tx.observe_pick(offers, count, SELECTED)
    tx.commit(SELECTED)
    tx.receipt_intent('Perversion', retained/'frame-0001.json')

    runner.step()

    assert events(evidence, 'floor_gift_receipt_recovered') == []
    assert (tx.data['pending'] or {}).get('kind') == 'receipt'
    assert tx.data['completed'] is False


def prepared_transaction(tmp_path, title='Perversion'):
    tx = FloorGiftTransaction(tmp_path/'tx.json')
    offers, count = offer(BEFORE)
    tx.prepare('scope', offers, count, BEFORE)
    tx.intent(title, count, BEFORE)
    offers, count = offer(SELECTED)
    tx.observe_pick(offers, count, SELECTED)
    tx.commit(SELECTED)
    return tx


def test_select_press_is_proven_by_the_notice_the_device_printed(tmp_path):
    """Live pi-20261014-072228: a notice naming a gift outside the selection is not a stop.

    The notice page and its own name plate are what prove the press submitted; which
    name the plate carries is the receipt stage's business, not the press's. Refusing it
    here stopped a real run after its input had already landed.
    """
    teams = (Team(2, frozenset({'Charge', 'Tremor'})),)
    ProfileStore(tmp_path/'user-team-profiles.json').save(teams)
    store = RunStore(tmp_path/'ledger.json', teams)
    scope = store.start()
    frames = [SELECTED, CONNECTING, LIVE_NOTICE]
    device = FakeDevice([cv2.imread(str(f.with_suffix('.png'))) for f in frames])
    runner = MirrorRunner(device, settings={'rounds': 2, 'interval': 0}, store=store,
                          run_id=scope, directory=tmp_path, journal=Journal(tmp_path),
                          observer=FrameObserver(tmp_path, [str(f) for f in frames]))
    tx = runner.floor_gift_transaction
    offers, count = offer(BEFORE)
    tx.prepare(scope, offers, count, BEFORE)
    tx.intent('Perversion', count, BEFORE)
    offers, count = offer(SELECTED)
    tx.observe_pick(offers, count, SELECTED)

    runner.step()

    result = runner.artifacts['steps'][-1]
    assert result['page_after'] == 'GIFT_GET' and result['passed'] is True
    assert device.clicks and len(device.swipes) == 0 and device.keys == []
    # The press is proven, nothing is claimed: the notice is still to be answered.
    assert tx.data['pending']['kind'] == 'commit'
    assert tx.data['receipts'] == [] and tx.data['completed'] is False
    outside = events(tmp_path, 'floor_gift_notice_outside_selection')
    assert len(outside) == 1
    assert outside[0]['printed'] == 'Dark Vestige' and outside[0]['selected'] == ['Perversion']


def test_a_notice_naming_no_pick_is_booked_with_the_name_the_device_printed(tmp_path):
    """The receipt keeps both names: the pick it answers and what the device printed.

    The notice's own Confirm lands on the floor's map, so this is the whole live shape:
    one pick, announced under a name the run never selected, and the receipt that says so.
    """
    tx = prepared_transaction(tmp_path)
    tx.receipt_intent('Dark Vestige', LIVE_NOTICE, on_notice_page=True)
    assert tx.data['pending']['kind'] == 'receipt'
    assert tx.data['pending']['title'] == 'Perversion'
    assert tx.data['pending']['printed'] == 'Dark Vestige'
    tx.observe_receipt('MAP', None, LIVE_NOTICE)
    assert tx.data['completed'] is True and tx.data['pending'] is None
    assert tx.data['receipts'][0]['title'] == 'Perversion'
    assert tx.data['receipts'][0]['printed'] == 'Dark Vestige'


def test_an_unmatched_notice_without_the_notice_page_still_refuses(tmp_path):
    """The reader is a loose middle-band match: only a notice page may explain a name.

    The encounter reward page prints '2~3 E.G.O Gift' straight into the same band, so a
    name the selection cannot account for is only accepted where the page proves a notice.
    """
    tx = prepared_transaction(tmp_path)
    with pytest.raises(ValueError):
        tx.receipt_intent('Dark Vestige', LIVE_NOTICE)


def test_notice_matches_a_pick_needs_a_printed_name_and_an_unclaimed_pick(tmp_path):
    tx = prepared_transaction(tmp_path)
    assert tx.notice_matches_a_pick('Dark Vestige') is True
    assert tx.notice_matches_a_pick(None) is False
    assert tx.notice_matches_a_pick('') is False
    tx.receipt_intent('Perversion', LIVE_NOTICE, on_notice_page=True)
    tx.observe_receipt('MAP', None, LIVE_NOTICE)
    assert tx.notice_matches_a_pick('Dark Vestige') is False
