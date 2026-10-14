"""The printed deployment order is read from several framings and adopted by agreement.

The native reader exists because the full-frame detector loses some of the small printed
digits (src/maalimbus/deployment_numbers_native.py). A number is adopted only when two
framings of that card's band read the same one, so these tests pin the ways that rule can go
wrong on a live page: a framing that clips the glyph, a framing that reads a different digit,
and a page where only one framing manages to read anything at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'agent')]

from maalimbus.deployment_numbers_native import CROP_BANDS, read_assignments  # noqa: E402
from maalimbus.team_vision import assignment_box  # noqa: E402
from maalimbus.vision import Text  # noqa: E402

CARD = (355, 236, 190, 248)
BAND = assignment_box(CARD)


class Reading:
    def __init__(self, text, score):
        self.text, self.score = text, score


class Detail:
    def __init__(self, rows):
        self.hit = bool(rows)
        self.filtered_results = rows


def scripted(answers, score=.97):
    """A stand-in native OCR that answers one framing at a time, in call order."""
    calls = []

    def native(kind, param, pixels):
        calls.append(param)
        index = len(calls) - 1
        text = answers[index] if index < len(answers) else None
        rows = [] if text is None else [Reading(text, score)]
        return Detail(rows)

    return native, calls


def read(answers, records=()):
    native, calls = scripted(answers)
    result, proof = read_assignments(native, object(), list(records), [CARD])
    return result, proof, calls


def test_two_framings_that_read_the_same_number_prove_it():
    result, proof, calls = read(['4', '4'])
    assert [item.text for item in result] == ['4']
    assert tuple(result[0].box) == tuple(BAND)
    assert result[0].score == pytest.approx(.97)
    assert proof[0]['agreement'] is True and proof[0]['card'] == 1
    assert len(calls) == 2, 'the third framing is not asked once two agree'


def test_a_glyph_only_one_framing_can_read_is_not_adopted():
    """The live failure: one framing read card 11's '4' while the others read nothing."""
    result, proof, _ = read(['4', None, None])
    assert result == []
    assert proof[0]['agreement'] is False


def test_framings_that_read_different_digits_are_not_adopted():
    result, proof, _ = read(['4', '5', None])
    assert result == [] and proof[0]['agreement'] is False


def test_the_framings_include_one_that_covers_the_narrowest():
    """The regression net: a nested set is what lost the glyph, not a missing print."""
    narrow = min(CROP_BANDS, key=lambda band: band[2] * band[3])
    covers = [band for band in CROP_BANDS
              if band is not narrow and band[0] <= narrow[0] and band[1] <= narrow[1]
              and band[0] + band[2] >= narrow[0] + narrow[2]
              and band[1] + band[3] >= narrow[1] + narrow[3]]
    assert covers, 'no framing keeps a margin on every side of the narrowest one'


def test_a_single_full_frame_reading_inside_the_band_is_replaced_not_kept():
    stray = Text('7', BAND, .99)
    result, proof, _ = read(['4', '4'], records=[stray])
    assert [item.text for item in result] == ['4'] and proof[0]['agreement'] is True


def test_an_unreadable_card_keeps_no_number_and_no_stray_reading():
    stray = Text('7', BAND, .99)
    result, proof, _ = read([None, None, None], records=[stray])
    assert result == [] and proof[0]['agreement'] is False


def test_a_missing_card_box_is_skipped_without_a_proof_row():
    native, calls = scripted(['4', '4'])
    result, proof = read_assignments(native, object(), [], [None])
    assert result == [] and proof == [] and calls == []
