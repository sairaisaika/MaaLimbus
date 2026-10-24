"""The battle HUD whose TURN caption the OCR drops is still the battle HUD (D99).

Live evidence `evidence/runtime/packaged-mirror-20261024-063400/frame-0024.png` is an
ordinary battle: `WAVE 1/1`, `TURN 5`, `MAX`, a party bar, `Win Rate` and `Damage`.  The
OCR read `WAVE` at 0.9999 and did not read `TURN` at all, so `battle_hud` refused and a
whole battle sat on `UNKNOWN` for 200 s with no click sent.
"""

import pathlib
import sys
from collections import namedtuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import battle_vision, vision  # noqa: E402

LOCALE = __import__('json').loads((ROOT / 'assets/resource/en/locale.json').read_text(encoding='utf-8'))

Text = namedtuple('Text', 'text box score')
SIZE = [1920, 1080]

# the recorded OCR of the live frame, verbatim
LIVE = [Text('WAVE', (22, 43, 44, 22), 0.999876),
        Text('Damage', (1476, 867, 68, 20), 0.998824),
        Text('Win', (1494, 796, 32, 19), 0.995737),
        Text('MAX', (1632, 37, 64, 40), 0.999917),
        Text('52', (1828, 488, 58, 52), 0.999564)]


def test_the_live_battle_frame_is_the_battle_hud():
    hud = battle_vision.battle_hud(LIVE, SIZE)
    assert hud is not None
    assert hud['wave'] is None and hud['turn'] is None
    assert hud['turn_box'] is None
    assert 'no turn submission or victory claim' in hud['scope']
    assert vision.classify(LIVE, LOCALE, SIZE) == 'BATTLE_HUD'


def test_the_controls_are_counted_in_their_own_bands():
    assert battle_vision.hud_controls(LIVE, SIZE) == 3          # MAX, Win, Damage
    assert battle_vision.hud_controls([Text('WAVE', (22, 43, 44, 22), .99)], SIZE) == 0


def test_a_single_control_is_not_enough():
    """One readable word is a coincidence; the page needs two of its own controls."""
    records = [Text('WAVE', (22, 43, 44, 22), .99), Text('MAX', (1632, 37, 64, 40), .99)]
    assert battle_vision.hud_controls(records, SIZE) == 1
    assert battle_vision.battle_hud(records, SIZE) is None
    assert vision.classify(records, LOCALE, SIZE) == 'UNKNOWN'


def test_a_frame_without_the_wave_caption_is_not_promoted_by_controls_alone():
    records = [Text('MAX', (1632, 37, 64, 40), .99), Text('Win', (1494, 796, 32, 19), .99)]
    assert battle_vision.hud_controls(records, SIZE) == 2
    assert battle_vision.battle_hud(records, SIZE) is None


def test_a_complete_hud_keeps_its_turn_caption():
    records = LIVE + [Text('TURN', (20, 97, 42, 22), 1.0), Text('5', (78, 97, 20, 22), .99)]
    hud = battle_vision.battle_hud(records, SIZE)
    assert hud is not None and hud['turn'] == '5'


def test_the_unreadable_signature_is_not_the_caption():
    """D100: the promoted HUD reports no values, so the progress guard sees blindness."""
    hud = battle_vision.battle_hud(LIVE, SIZE)
    assert hud['wave'] is None and hud['turn'] is None


def test_a_blind_fight_that_keeps_moving_is_not_a_stall():
    from maalimbus.runner import battle_progress

    state = {}
    verdicts = [battle_progress(state, (None, None), rounds=3, frame=f'frame-{n}')
                for n in range(40)]
    assert set(verdicts) == {'progress'}


def test_a_blind_fight_on_a_frozen_frame_still_ends():
    from maalimbus.runner import battle_progress

    state = {}
    verdicts = [battle_progress(state, (None, None), rounds=3, frame='same')
                for _ in range(20)]
    assert verdicts[0] == 'progress' and verdicts[-1] == 'blind_long'


def test_a_read_signature_still_decides_on_its_numbers():
    from maalimbus.runner import battle_progress

    state = {}
    assert [battle_progress(state, ('1/1', '4'), rounds=3, frame='a') for _ in range(3)] == ['progress'] * 3
    assert battle_progress(state, ('1/1', '4'), rounds=3, frame='b') == 'stalled'
    assert battle_progress(state, ('1/1', '5'), rounds=3, frame='c') == 'progress'
