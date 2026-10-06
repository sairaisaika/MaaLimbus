"""The event page's choice column (no device, no image)."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.event_vision import (OPTION_BAND, choice_options, gift_hints,
                                    preferred_choice)  # noqa: E402

SIZE = (1920, 1080)


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
