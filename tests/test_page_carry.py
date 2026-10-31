from __future__ import annotations
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from maalimbus.page_carry import carry_page


def test_the_same_bytes_keep_the_map():
    assert carry_page('UNKNOWN', 'MAP', 'abc', 'abc') == 'MAP'


def test_a_different_picture_is_still_unknown():
    assert carry_page('UNKNOWN', 'MAP', 'abc', 'def') == 'UNKNOWN'


def test_a_named_page_is_never_overridden():
    assert carry_page('SHOP', 'MAP', 'abc', 'abc') == 'SHOP'


def test_only_a_map_is_carried():
    assert carry_page('UNKNOWN', 'SHOP', 'abc', 'abc') == 'UNKNOWN'


def test_missing_hashes_carry_nothing():
    assert carry_page('UNKNOWN', 'MAP', None, 'abc') == 'UNKNOWN'
    assert carry_page('UNKNOWN', 'MAP', 'abc', None) == 'UNKNOWN'
