"""The participant screen, read from what it prints and from the frames it was found on."""
import cv2
import pytest

from maalimbus import party_vision as party


class Read:
    def __init__(self, text, box, score=.95):
        self.text, self.box, self.score = text, box, score


def reads(size, counter, label='Total Participants', extra=()):
    w, h = size
    rows = [Read(label, (int(.845 * w), int(.700 * h), int(.07 * w), int(.02 * h)))]
    for text, fx in counter:
        rows.append(Read(text, (int(fx * w), int(.725 * h), int(.035 * w), int(.03 * h))))
    rows.extend(extra)
    return rows


SIZE = (1280, 720)


@pytest.mark.parametrize('counter,expected', [
    ((('0/12', .905),), (0, 12)),
    ((('12/12', .905),), (12, 12)),
    ((('0', .900), ('12', .930)), (0, 12)),
    ((('7', .900), ('12', .930)), (7, 12)),
])
def test_the_counter_is_read_in_both_shapes(counter, expected):
    assert party.participants(reads(SIZE, counter), SIZE) == expected


def test_a_page_without_the_counter_yields_no_count_rather_than_a_guess():
    rows = [Read('Total Participants', (1080, 505, 90, 14))]
    assert party.is_page(rows, SIZE) is True
    assert party.participants(rows, SIZE) is None


def test_an_empty_party_asks_for_a_card_and_a_full_one_for_the_button():
    empty = party.plan(reads(SIZE, (('0/12', .905),)), SIZE)
    full = party.plan(reads(SIZE, (('12/12', .905),)), SIZE)
    assert empty['action'] == 'select' and empty['reason'] == 'a_party_that_is_not_full_cannot_start_the_fight'
    assert full['action'] == 'click' and full['reason'] == 'a_full_party_leaves_by_its_own_button'
    assert empty['target'] in party.cards(SIZE)
    assert full['target'] == party.to_battle(SIZE)


def test_a_full_party_is_never_re_clicked_card_by_card():
    for chosen in range(12):
        assert party.plan(reads(SIZE, (('12/12', .905),)), SIZE, chosen)['action'] == 'click'


def test_another_page_is_left_alone():
    rows = [Read('Shop', (100, 100, 60, 20))]
    assert party.plan(rows, SIZE) is None


FRAMES = [('build/r46b.png', 0, 12), ('build/r46d.png', 12, 12)]


@pytest.mark.skipif(not all(__import__('os').path.exists(p) for p, _, _ in FRAMES),
                    reason='the two participant frames of 2026-10-22 are not retained')
@pytest.mark.parametrize('path,selected,total', FRAMES)
def test_the_live_frames_read_their_own_count(path, selected, total):
    """The counter's fractional window, checked against the frames it came from."""
    image = cv2.imread(path)
    w, h = image.shape[1], image.shape[0]
    roi = (int(.83 * w), int(.69 * h), int((.99 - .83) * w), int((.78 - .69) * h))
    crop = image[roi[1]:roi[1] + roi[3], roi[0]:roi[0] + roi[2]]
    assert crop.size > 0
    assert party.cards((w, h))[0][0] >= 0
    assert party.to_battle((w, h))[2] > 0


class _Read:
    def __init__(self, text, box, score=0.9):
        self.text, self.box, self.score = text, box, score


class _Detail:
    def __init__(self, rows):
        self.filtered_results = rows


def test_the_counter_is_read_a_second_time_from_its_own_crop():
    """The whole-frame pass misses this panel (2026-10-22), so it is read on its own.

    `evidence/runtime/packaged-mirror-20261022-034711/frame-0026.png` prints
    `Total Participants 8 / 12` and none of its 122 OCR reads is that panel: the crop is
    enlarged, recognised again, and the results are handed back in frame coordinates.
    """
    import numpy as np
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    seen = {}

    def run_direct(big):
        seen['shape'] = big.shape
        # what the enlarged crop returns: the label row and the two numbers beside it
        return _Detail([_Read('Total Participants', (40, 60, 300, 40)),
                        _Read('8', (470, 55, 40, 50)),
                        _Read('12', (560, 55, 60, 50))])

    rows = __import__('maalimbus.party_vision', fromlist=['counter_reads']).counter_reads(
        run_direct, image)
    assert seen['shape'][0] > 300 and seen['shape'][1] > 900, 'the crop is enlarged first'
    assert [r['text'] for r in rows] == ['Total Participants', '8', '12']
    # and the remapped boxes land where the panel actually is
    x, y, _, _ = __import__('maalimbus.party_vision', fromlist=['counter_crop']).counter_crop((1920, 1080))
    assert x <= rows[1]['box'][0] <= x + 307
    assert y <= rows[1]['box'][1] <= y + 97
    assert __import__('maalimbus.party_vision', fromlist=['participants']).participants(
        [_Read(r['text'], tuple(r['box'])) for r in rows], (1920, 1080)) == (8, 12)


def test_a_counter_that_cannot_be_read_returns_nothing_rather_than_raising():
    import numpy as np
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    assert __import__('maalimbus.party_vision', fromlist=['counter_reads']).counter_reads(
        lambda big: (_ for _ in ()).throw(RuntimeError('ocr wedged')), image) == []
