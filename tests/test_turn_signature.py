"""The turn badge's signature keeps the glyph and drops the badge's glow (D156)."""

import json
import pathlib

import cv2
import numpy as np
import pytest

from maalimbus import battle_vision


def _board(glyph, brightness=0):
    """A board whose TURN badge area draws `glyph` on a constant background."""
    image = np.full((1080, 1920, 3), 20 + brightness, np.uint8)
    height = int(round(battle_vision.TURN_BADGE[1] * 1080))
    width = int(round(battle_vision.TURN_BADGE[0] * 1920))
    cell_h = int(round(battle_vision.TURN_BADGE[3] * 1080))
    cell_w = int(round(battle_vision.TURN_BADGE[2] * 1920))
    for y, row in enumerate(glyph):
        for x, pixel in enumerate(row):
            if pixel:
                image[height + y * cell_h // len(glyph),
                      width + x * cell_w // len(row)] = 230 + brightness
    return image

ARCHIVE = pathlib.Path('evidence/runtime/packaged-mirror-20261024-193857')


def _board(fill):
    """A board whose badge crop is `fill` (a fraction of the crop painted bright)."""
    image = np.full((1080, 1920, 3), 20, np.uint8)
    fx, fy, fw, fh = battle_vision.TURN_BADGE
    x, y = int(fx * 1920), int(fy * 1080)
    w, h = int(fw * 1920), int(fh * 1080)
    painted = int(round(h * fill))
    if painted:
        image[y:y + painted, x:x + w] = 235
    return image


def test_the_same_glyph_under_a_different_glow_reads_the_same():
    assert battle_vision.turn_signature(_board(0.55)) == battle_vision.turn_signature(
        _board(0.55))


def test_a_brightness_shift_is_not_a_new_turn():
    before = battle_vision.turn_signature(_board(0.55))
    lifted = (_board(0.55).astype(np.int16) + 30).clip(0, 255).astype(np.uint8)
    after = battle_vision.turn_signature(lifted)
    assert not battle_vision.turn_changed(before, after)


def test_a_different_glyph_is_a_different_turn():
    before = battle_vision.turn_signature(_board(0.35))
    after = battle_vision.turn_signature(_board(0.85))
    assert battle_vision.turn_changed(before, after)


def test_a_missing_frame_has_no_signature():
    assert battle_vision.turn_signature(None) is None


@pytest.mark.skipif(not ARCHIVE.exists(), reason='the retained fight is not in this checkout')
def test_one_fight_yields_a_handful_of_turn_pictures():
    """The live noise that motivated D156: 26 consecutive reads, 23 raw distinct values."""
    readings = []
    for png in sorted(ARCHIVE.glob('frame-*.png')):
        meta = png.with_suffix('.json')
        if not meta.exists():
            continue
        if json.loads(meta.read_text(encoding='utf-8')).get('scene') != 'BATTLE_HUD':
            continue
        image = cv2.imread(str(png))
        if image is None:
            continue
        signature = battle_vision.turn_signature(image)
        if signature:
            readings.append(tuple(signature))
    assert len(readings) >= 20
    assert len(set(readings)) <= 15, f'{len(set(readings))} pictures for one fight'


def test_the_crop_sits_beside_the_turn_caption():
    """The badge crop is the strip right of the caption, not the row above it.

    `packaged-mirror-20261025-014906/frame-0004.json` prints the `TURN` caption at
    [20,97,42,22] of 1920x1080; the old box (0.050,0.074,...) started at y=80 and read a
    flat strip, so 16 archived battle frames of `...-20261024-171103` produced one value
    before this change and three after.
    """
    from maalimbus.battle_vision import TURN_BADGE
    cx, cy, cw, ch = 20 / 1920, 97 / 1080, 42 / 1920, 22 / 1080
    x, y, w, h = TURN_BADGE
    assert x > cx + cw, 'the crop starts right of the caption'
    assert y >= cy - 0.01, 'and in the caption row, not the row above'
    assert h <= ch + 0.006 and w <= 0.06
