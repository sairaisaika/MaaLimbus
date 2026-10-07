"""The tried-spot memory that keeps the window from replaying a swallowed click."""
from maalimbus.map_progress import MapProgress


def test_a_named_new_floor_starts_a_new_layout():
    progress = MapProgress()
    assert progress.note_floor(3) == 3
    progress.note_click([303, 708, 40, 40])
    assert progress.remaining([[303, 708, 40, 40], [681, 441, 40, 40]]) == [[681, 441, 40, 40]]
    assert progress.note_floor(4) == 4
    assert progress.remaining([[303, 708, 40, 40]]) == [[303, 708, 40, 40]]


def test_a_dropped_floor_reading_keeps_the_spots_already_tried():
    """Live run build/window-run110.json: the reading flickered 3 / None / 3.

    Every flicker used to clear the tried set, so the window re-clicked the same two
    40x40 icons eight times ([681,441], [748,416], [681,441], [748,416] ...) while the
    reachable "?" node at [303,708] sat untried in the same candidate list.
    """
    progress = MapProgress()
    progress.note_floor(3)
    progress.note_click([681, 441, 40, 40])
    progress.note_click([748, 416, 40, 40])
    for reading in (None, 3, None, 3):
        assert progress.note_floor(reading) == 3
    assert progress.remaining([[681, 441, 40, 40], [748, 416, 40, 40],
                               [303, 708, 40, 40]]) == [[303, 708, 40, 40]]


def test_a_first_reading_that_is_missing_still_leaves_the_floor_unnamed():
    progress = MapProgress()
    assert progress.note_floor(None) is None
    progress.note_click([1, 2, 3, 4])
    assert progress.remaining([[1, 2, 3, 4]]) == []
    assert progress.note_floor(2) == 2
    assert progress.remaining([[1, 2, 3, 4]]) == [[1, 2, 3, 4]]
