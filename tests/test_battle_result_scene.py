"""The victory screen's producer, pinned to the real frames that proved it.

`BATTLE_RESULT` is consumed by the pipeline (`PostBattleObserve` in
`assets/resource/base/pipeline/mirror.json`) and was, until now, only ever an
expected successor in `window.py` -- nothing produced it. These cases hold the
producer to the two archived frames it was derived from, including the negative
control: removing the caption must stop the screen from being named, otherwise
the branch is being lit up by something other than the victory caption.
"""

import json
from pathlib import Path

from maalimbus.vision import Text, classify

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / 'assets' / 'resource'
FRAMES = ROOT / 'evidence' / 'runtime' / 'window-20261006-105647'


def test_the_victory_caption_is_what_names_the_result_screen():
    words = json.loads((LOCALES / 'en' / 'locale.json').read_text(encoding='utf-8'))
    assert words['victory'] == '^VICTORY$'
    for name in ('frame-0066.json', 'frame-0067.json'):
        data = json.loads((FRAMES / name).read_text(encoding='utf-8'))
        records = [Text(t['text'], tuple(t['box']), t['score']) for t in data['ocr']]
        assert classify(records, words, tuple(data['size'])) == 'BATTLE_RESULT', name
        without = [r for r in records if r.text != 'VICTORY']
        assert classify(without, words, tuple(data['size'])) != 'BATTLE_RESULT', name
