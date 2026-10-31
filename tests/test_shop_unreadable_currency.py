"""余额读不到时，购买意图不能被判死（D421）。"""
from __future__ import annotations

import pathlib

SOURCE = (pathlib.Path(__file__).resolve().parents[1]
          / 'src' / 'maalimbus' / 'shop_transaction.py')


def test_an_unreadable_counter_keeps_the_intent():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'if coins is None and shelf:' in source
    assert 'unverified_attempts' in source
    assert 'the_currency_counter_is_unreadable_on_this_frame' in source
    assert 'return False' in source.split('if coins is None and shelf:')[1][:1500]


def test_the_refusal_is_still_there_for_a_counter_that_disagrees():
    source = SOURCE.read_text(encoding='utf-8')
    assert "raise ValueError('Exact shop purchase currency delta not proven')" in source
