"""The saved-team header, in both wordings the page has used.

The check that shipped for this header never fired live: every pre-battle frame
in the corpus prints ``Preset #1`` at [150,254,84,21] (score .9098), while the
reader understood only ``TEAMS #N`` inside a band that starts at x=0.16. These
tests pin the measured box, both words, and the refusals that keep a guess out.
"""
import json
import pathlib

import pytest

from maalimbus.runner import gift_slot, team_state, team_verdict
from maalimbus.team_vision import (TEAM_HEADER_ROI, TEAM_HEADER_SCORE, card_states,
                                   saved_team_header, selected_saved_team)
from maalimbus.vision import Text

ROOT = pathlib.Path(__file__).resolve().parents[1]
SIZE = (1920, 1080)
#: Measured on packaged-mirror-20261024-042500/frame-0014.json (and two others).
LIVE_BOX = (150, 254, 84, 21)


def header(text, box=LIVE_BOX, score=0.9098):
    return [Text(text, tuple(box), score)]


def test_the_live_wording_names_its_slot():
    # The header is also the control, so its box travels with the answer (D117).
    assert saved_team_header(header('Preset #1'), SIZE) == {
        'slot': 1, 'word': 'preset', 'box': (150, 254, 84, 21)}
    assert selected_saved_team(header('Preset #1'), SIZE) == 1


def test_the_other_wording_is_still_understood():
    assert saved_team_header(header('TEAMS #2'), SIZE) == {'slot': 2, 'word': 'teams', 'box': None}
    assert selected_saved_team(header('TEAM #3'), SIZE) == 3


def test_the_measured_box_is_inside_the_band():
    x, y, w, h = LIVE_BOX
    left, top, right, bottom = TEAM_HEADER_ROI
    assert left * SIZE[0] <= x + w / 2 <= right * SIZE[0]
    assert top * SIZE[1] <= y + h / 2 <= bottom * SIZE[1]
    assert TEAM_HEADER_SCORE <= 0.9098, 'the live score must clear the threshold'


def test_a_header_outside_the_band_is_not_read():
    assert saved_team_header(header('Preset #1', box=(1500, 900, 84, 21)), SIZE) is None


def test_a_partial_wording_is_not_a_slot():
    for text in ('Preset', 'Preset #', '#1', 'Preset #0', 'Preset #41', 'Presets #1'):
        assert selected_saved_team(header(text), SIZE) is None, text


def test_two_headers_are_a_question_not_a_guess():
    assert saved_team_header(header('Preset #1') + header('Preset #2', box=(320, 254, 84, 21)), SIZE) is None


def test_a_low_score_is_not_a_read():
    assert selected_saved_team(header('Preset #1', score=0.40), SIZE) is None


def test_the_page_record_carries_the_word_it_used():
    record = {'size': list(SIZE), 'ocr': [{'text': 'Preset #1', 'box': list(LIVE_BOX), 'score': 0.9098}],
              'local_ocr': []}
    controls = {'pre_battle.card_%02d' % i: (100 * i, 500, 80, 120) for i in range(1, 13)}
    state = team_state(record, controls)
    assert state is not None
    assert state['saved_team'] == 1
    assert state['saved_team_word'] == 'preset'


def test_a_page_without_a_header_says_nothing():
    record = {'size': list(SIZE), 'ocr': [{'text': '12/12', 'box': [1700, 754, 122, 57], 'score': 0.99}],
              'local_ocr': []}
    controls = {'pre_battle.card_%02d' % i: (100 * i, 500, 80, 120) for i in range(1, 13)}
    state = team_state(record, controls)
    assert state['saved_team'] is None and state['saved_team_word'] is None


def test_the_verdict_still_refuses_to_guess():
    assert team_verdict(None, 2)['kind'] is None
    assert team_verdict(2, None)['kind'] is None
    assert team_verdict(1, 2) == {'kind': 'mismatch', 'seen': 1, 'wanted': 2}
    assert gift_slot(1, 2) == 1 and gift_slot(None, 2) == 2


def test_the_archived_frames_agree():
    frames = sorted((ROOT / 'evidence' / 'runtime').glob('packaged-mirror-20261024-*/frame-*.json'))
    seen = 0
    for path in frames:
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if record.get('scene') != 'PRE_BATTLE_TEAM':
            continue
        records = [Text(item['text'], tuple(item['box']), item['score'])
                   for item in record.get('ocr') or []]
        slot = selected_saved_team(records, tuple(record['size']))
        assert slot is not None, path.name
        seen += 1
    if seen == 0:
        pytest.skip('no pre-battle frame in the archive')

def test_a_teams_header_outranks_the_preset_number_beside_it():
    """The old page shows both words; the header is the TEAMS one, not the preset."""
    records = [Text('TEAMS #2', (336, 176, 120, 28), 0.99),
               Text('Preset #1', (150, 255, 110, 24), 0.99),
               Text('TEAMS #1', (150, 450, 120, 28), 0.99)]
    assert saved_team_header(records, SIZE) == {'slot': 2, 'word': 'teams', 'box': None}
    assert selected_saved_team(records, SIZE) == 2


def test_a_preset_only_page_is_read_because_the_build_prints_nothing_else():
    records = [Text('Preset #1', (150, 255, 110, 24), 0.99)]
    assert saved_team_header(records, SIZE) == {'slot': 1, 'word': 'preset', 'box': (150, 255, 110, 24)}

def test_a_preset_is_not_a_team_on_a_page_that_speaks_teams():
    """The loadout picker shows a preset number and TEAMS rows; only TEAMS counts."""
    records = [Text('Preset #1', (150, 255, 110, 24), 0.99),
               Text('TEAMS #1', (150, 450, 120, 28), 0.99)]
    assert saved_team_header(records, SIZE) is None
