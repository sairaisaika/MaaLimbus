"""兜底时火苗与格子辉光冲突，取火苗。"""
from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from maalimbus import map_vision as mv


def test_only_the_flame_speaks():
    assert mv.pick_party_fallback(None, (862, 541)) == (862, 541)


def test_only_the_glow_speaks():
    assert mv.pick_party_fallback((576, 687), None) == (576, 687)


def test_a_far_apart_pair_keeps_the_flame():
    # the measured frame: flame (862,541) is the party, glow (576,687) is a node
    assert mv.pick_party_fallback((576, 687), (862, 541)) == (862, 541)


def test_a_close_pair_keeps_the_glow():
    assert mv.pick_party_fallback((860, 560), (862, 541)) == (860, 560)


def test_neither_answers():
    assert mv.pick_party_fallback(None, None) is None
