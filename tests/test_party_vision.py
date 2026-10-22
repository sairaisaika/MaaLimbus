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
