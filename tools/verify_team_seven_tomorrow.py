"""Read-only audit of Team7's free Tomorrow's Fortune receipt, not a floor clear."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from maalimbus.initial_gifts import receipt_name
from maalimbus.vision import Text


def main():
    tx = json.loads((ROOT / 'config/user-floor-gift-transaction.json').read_text())
    candidates = [tx] + tx.get('history', [])
    matches = [t for t in candidates if t['scope'] == '4734bfe68803421c8d261dccbc9120be'
               and t['selected'] == ["Tomorrow's Fortune"] and t['completed']]
    assert len(matches) == 1
    tx = matches[0]
    assert tx['pending'] is None and len(tx['receipts']) == 1
    entry = tx['receipts'][0]
    path = Path(entry['receipt'])
    data = json.loads(path.read_text())
    sha = hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()
    assert sha == data['image_sha256'] and data['scene'] == 'GIFT_GET'
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in data['ocr']]
    assert receipt_name(records, data['size']) == entry['title'] == "Tomorrow's Fortune"
    successor = Path(entry['successor'])
    after = json.loads(successor.read_text())
    assert hashlib.sha256(successor.with_suffix('.png').read_bytes()).hexdigest() == after['image_sha256']
    assert after['scene'] == 'MAP'
    output = ROOT / 'build/team-seven-tomorrow-real-verification.json'
    output.write_text(json.dumps(dict(scope=tx['scope'], title=entry['title'],
        receipt=str(path), png_sha256=sha, successor=str(successor),
        device_input=False, floor_clear=False), indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
