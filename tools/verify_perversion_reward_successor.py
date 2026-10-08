"""Reconcile one retained GET acknowledgement; never repeat device input."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.initial_gifts import receipt_name
from maalimbus.runner import unselected_reward_successor
from maalimbus.vision import Text


def main():
    directory = ROOT/'evidence/runtime/window-20261008-111130'
    result = json.loads((directory/'result.json').read_text())
    step = result['steps'][0]
    tx = FloorGiftTransaction(ROOT/'config/user-floor-gift-transaction.json')
    pending = tx.data['pending']
    ledger = json.loads((ROOT/'config/user-run-ledger.json').read_text())
    assert tx.data['scope'] == ledger['active']['id'] == result['run_ledger']['run']
    assert pending['kind'] == 'receipt' and pending['title'] == 'Perversion'
    assert Path(pending['proof']).resolve() == (directory/'frame-0001.json').resolve()
    assert result['clicks_sent'] == step['clicks_sent'] == 1
    assert step['page_before'] == 'GIFT_GET' and step['page_after'] == 'REWARD_CARD'
    assert step['reason'] == 'floor_gift_receipt_successor_not_proven'
    assert step['plan']['reason'] == 'the_gift_get_notice_is_cleared_with_its_own_confirm'
    x, y, w, h = step['plan']['target']; px, py = step['click_point']
    assert x <= px < x+w and y <= py < y+h
    hashes = []
    for index, key in ((1, 'observation'), (2, 'settled')):
        frame = directory/f'frame-{index:04}.json'
        data = json.loads(frame.read_text())
        digest = hashlib.sha256(frame.with_suffix('.png').read_bytes()).hexdigest()
        assert digest == data['image_sha256'] == step[key]['image_sha256']
        hashes.append(digest)
        if index == 1:
            records = [Text(r['text'], tuple(r['box']), r['score']) for r in data['ocr']]
            assert receipt_name(records, data['size']) == 'Perversion'
        else:
            assert data['scene'] == 'REWARD_CARD'
            reward = unselected_reward_successor(data)
            assert reward
    tx.observe_receipt('REWARD_CARD', None, frame, next_reward_offer=reward)
    output = ROOT/'build/perversion-receipt-real-verification-20261008.json'
    output.write_text(json.dumps(dict(scope=tx.data['scope'], receipt=pending['proof'],
        successor=str(frame), hashes=hashes, device_input=False,
        gift_completed=tx.data['completed'], floor_clear_verified=False), indent=2)+'\n')
    print(output)


if __name__ == '__main__':
    main()
