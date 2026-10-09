"""Bind Team7's first clear to actual named GETs and the floor2 successor."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from maalimbus.initial_gifts import receipt_name
from maalimbus.theme_vision import selection_floor
from maalimbus.storage import ProfileStore, RunStore
from maalimbus.vision import Text


def main():
    tx = json.loads((ROOT / 'config/user-floor-gift-transaction.json').read_text())
    ledger = json.loads((ROOT / 'config/user-run-ledger.json').read_text())
    assert tx['scope'] == ledger['active']['id'] == '4734bfe68803421c8d261dccbc9120be'
    assert ledger['active']['team'] == 7
    assert tx['completed'] and tx['pending'] is None
    assert set(tx['selected']) == {'Broken Revolver', 'Blood, Sweat, and Tears'}
    assert len(tx['receipts']) == 2
    proofs = []
    for entry in tx['receipts']:
        path = Path(entry['receipt'])
        data = json.loads(path.read_text())
        sha = hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()
        assert sha == data['image_sha256'] and data['scene'] == 'GIFT_GET'
        records = [Text(t['text'], tuple(t['box']), t['score']) for t in data['ocr']]
        assert receipt_name(records, data['size']) == entry['title']
        proofs.append(dict(title=entry['title'], frame=str(path), png_sha256=sha))
    successor = Path(tx['receipts'][-1]['successor'])
    data = json.loads(successor.read_text())
    assert hashlib.sha256(successor.with_suffix('.png').read_bytes()).hexdigest() == data['image_sha256']
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in data['ocr']]
    assert data['scene'] == 'THEME_PACKS' and selection_floor(records, data['size']) == 2
    profiles = ProfileStore(ROOT / 'config/user-team-profiles.json').load()
    teams = [next(t for t in profiles if t.slot == slot) for slot in ledger['team_slots']]
    RunStore(ROOT / 'config/user-run-ledger.json', teams).record(
        tx['scope'], 'floor_clear-1', 'floor_clear', successor, floor=1)
    output = ROOT / 'build/team-seven-floor-one-real-verification.json'
    output.write_text(json.dumps(dict(scope=tx['scope'], verified_floor=1,
        device_input=False, receipts=proofs, successor=str(successor), next_floor=2,
        final_payout_verified=False), indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
