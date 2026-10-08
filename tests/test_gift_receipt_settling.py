"""Retained Select/CONNECTING/GET sequence, driven without a controller."""
import json
from pathlib import Path

import cv2
import pytest

from maalimbus.floor_gifts import observe
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.runner import FakeDevice, FrameObserver, MirrorRunner, unselected_reward_successor
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.storage import ProfileStore, RunStore
from maalimbus.vision import Text

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT/'evidence/runtime/window-20261008-102111/frame-0435.json'
SELECTED = ROOT/'evidence/runtime/window-20261008-110526/frame-0001.json'
CONNECTING = SELECTED.with_name('frame-0002.json')
GET = ROOT/'evidence/runtime/window-20261008-110924/frame-0001.json'


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
