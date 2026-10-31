"""`map_click_size` 必须进日志，而不是只躺在 record 里。"""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_the_size_record_is_named_by_the_debug_note():
    source = (REPO / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    assert "'map_click_size'" in source
    start = source.index('_debug = {name: record[name] for name in')
    block = source[start:start + 700]
    assert "'map_click_size'" in block
