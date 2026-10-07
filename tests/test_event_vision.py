"""The event page's choice column and skill check (no device)."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.event_vision import (ODDS_TEMPLATE_DIR, OPTION_BAND,
                                    best_check_choice, check_box, choice_options,
                                    gift_hints, odds_scores,
                                    preferred_choice)  # noqa: E402

SIZE = (1920, 1080)

#: the lived skill check page, kept in the repository as evidence.
CHECK_FRAME = ROOT / 'evidence/runtime/window-20261006-204421/frame-0001.png'


def token(text, box, score=0.99):
    return {'text': text, 'box': list(box), 'score': score}


# evidence/runtime/window-20261006-044943/frame-0015.json, the lived page.
LIVE = [token('00:00:07:96', (122, 200, 128, 22)),
        token('45', (124, 1002, 28, 26)),
        token('REC', (868, 200, 62, 22)),
        token('Choices', (1050, 166, 168, 46), 1.0),
        token('I think we will smile.', (1096, 311, 290, 28), 0.956),
        token("Don't make any expression.", (1096, 464, 378, 28), 0.99),
        token('Select to gain a Blunt E.G.O Gift', (1096, 500, 322, 26), 0.995),
        token('Cry and cry until you sink.', (1096, 643, 366, 33), 0.997)]


def test_the_live_choice_column_reads_three_rows_and_one_hint():
    options = choice_options(LIVE, SIZE)
    assert [text for _box, text in options] == ['I think we will smile.',
                                                "Don't make any expression.",
                                                'Cry and cry until you sink.']
    # Top to bottom, so the boxes come back in screen order.
    assert [box[1] for box, _text in options] == [311, 464, 643]
    assert gift_hints(LIVE, SIZE) == [500]


def test_the_hinted_row_is_the_one_taken():
    options = choice_options(LIVE, SIZE)
    hints = gift_hints(LIVE, SIZE)
    # "Select to gain a Blunt E.G.O Gift" sits under "Don't make any expression.",
    # so that row is the one whose reward is named.
    assert preferred_choice(options, hints) == 1
    # No hint, or no options at all: the first row is still one bounded input.
    assert preferred_choice(options, []) == 0
    assert preferred_choice([], hints) == 0
    # A hint far below every row never claims one.
    assert preferred_choice(options, [900]) == 0


def test_short_tokens_and_rows_outside_the_column_are_not_choices():
    outside = [token('Some long line of speech', (200, 311, 300, 28)),
               token('Choices', (1050, 166, 168, 46), 1.0),
               token('REC', (868, 200, 62, 22)),
               token('23/45', (1096, 500, 100, 30))]
    assert choice_options(outside, SIZE) == []
    assert choice_options(LIVE, None) == []
    x0, y0, x1, y1 = OPTION_BAND
    inside = [token('A line that is long enough', (int(1920 * (x0 + x1) / 2),
                                                   int(1080 * (y0 + y1) / 2), 300, 28))]
    assert len(choice_options(inside, SIZE)) == 1


def test_the_live_skill_check_row_reads_all_twelve_odds_and_picks_the_best():
    cv2 = pytest.importorskip('cv2')
    if not CHECK_FRAME.exists():
        pytest.skip('the live check frame is not in this checkout')
    image = cv2.imread(str(CHECK_FRAME))
    scores = odds_scores(image, directory=ROOT / ODDS_TEMPLATE_DIR)
    # Hand-read from the frame: VeryHigh, VeryLow, VeryHigh, VeryHigh, High, High,
    # VeryLow, VeryLow, Normal, Normal, VeryLow, VeryLow.
    assert [item['tier'] for item in scores] == [
        'very_high', 'very_low', 'very_high', 'very_high', 'high', 'high',
        'very_low', 'very_low', 'normal', 'normal', 'very_low', 'very_low']
    # Every slot is read well clear of the trust threshold, so the tie-break below is
    # the only thing that can move the choice.
    assert all(item['score'] >= 0.9 for item in scores)
    assert best_check_choice(scores) == 1


def test_a_slot_with_unreadable_odds_is_never_chosen():
    scores = [{'index': 1, 'tier': None, 'score': 0.71},
              {'index': 2, 'tier': 'normal', 'score': 0.95},
              {'index': 3, 'tier': 'high', 'score': 0.93}]
    assert best_check_choice(scores) == 3
    # A tie keeps the leftmost slot, and nothing trusted means no choice at all.
    assert best_check_choice([{'index': 4, 'tier': 'high', 'score': 0.99},
                              {'index': 5, 'tier': 'high', 'score': 0.97}]) == 4
    assert best_check_choice([{'index': 1, 'tier': None, 'score': 0.9}]) is None
    assert best_check_choice([]) is None
    assert best_check_choice(None) is None


def test_every_check_box_sits_on_its_own_card():
    first = check_box(1, (1920, 1080))
    assert abs(first[0] + first[2] / 2 - 0.0617 * 1920) <= 2
    last = check_box(12, (1920, 1080))
    assert abs(last[0] + last[2] / 2 - (0.0617 + 0.05398 * 11) * 1920) <= 2
    # The cards are the bright row under the captions (y 922-1035 of 1080).
    assert first[1] >= 920 and first[1] + first[3] <= 1040
    # A narrower frame scales: the same slot's box is half as wide at 960.
    assert check_box(1, (960, 540))[2] == first[2] // 2
