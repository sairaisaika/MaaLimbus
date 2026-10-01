import json
from pathlib import Path

import pytest

from maalimbus.vision import Text, classify, inset_box


LOCALES = Path(__file__).resolve().parents[1] / 'assets/resource'


@pytest.mark.parametrize('locale,mirror,inferno,enter,exploring', [
    ('en', 'Mirror', 'Inferno', 'Enter', 'Before Entry'),
    ('jp', '鏡ダンジョン', '地獄', '入場', '探索状況'),
])
def test_stable_words_and_position_ignore_artwork_and_values(locale, mirror, inferno, enter, exploring):
    words = json.loads((LOCALES / locale / 'locale.json').read_text(encoding='utf-8'))
    drive = [Text(mirror, (300, 400, 100, 30), .99), Text(inferno, (820, 100, 100, 40), .99)]
    assert classify(drive, words, (1000, 1000)) == 'DRIVE'
    entry = [Text(enter, (830, 680, 80, 35), .99), Text(exploring, (760, 160, 100, 30), .99), Text('7498', (800, 70, 100, 30), .99)]
    assert classify(entry, words, (1000, 1000)) == 'MIRROR_ENTRY'
    assert classify(entry[:-1], words, (1000, 1000)) == 'MIRROR_ENTRY'
    assert classify([Text(enter, (100, 100, 80, 35), .99)], words, (1000, 1000)) == 'UNKNOWN'


def test_resource_dialog_wins_over_menu():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    records = [Text('Mirror', (300, 400, 100, 30), .99), Text('Inferno', (820, 100, 100, 40), .99), Text('Purchase Lunacy', (400, 400, 200, 40), .99)]
    assert classify(records, words, (1000, 1000)) == 'RESOURCE_DIALOG'


def test_retained_drive_truncated_menu_needs_independent_heading():
    words = json.loads((LOCALES / 'en/locale.json').read_text())
    records = [Text('Mirro', (300, 400, 100, 30), .92), Text('Inferno', (820, 100, 100, 40), .99)]
    assert classify(records, words, (1000, 1000)) == 'DRIVE'
    assert classify(records[:1], words, (1000, 1000)) == 'UNKNOWN'
    assert classify([Text('MIRROR OF', (300, 400, 100, 30), .99), records[1]], words, (1000, 1000)) == 'UNKNOWN'


def test_box_inset_always_remains_inside_recognition():
    for width in (1, 2, 5, 100):
        x, y, w, h = inset_box((10, 20, width, width))
        assert 10 <= x < x + w <= 10 + width
        assert 20 <= y < y + h <= 20 + width
