"""The pause panel states the run's real progress; these pin that reading."""
from maalimbus.dungeon_progress import dungeon_progress, steps_left
from maalimbus.vision import Text

SIZE = (1280, 720)


def box(cx, cy, bw=80, bh=26):
    return (int(cx - bw / 2), int(cy - bh / 2), bw, bh)


def panel(**overrides):
    """The live panel from build/r8-menu2.png, floored at floor 1 (HARD) 4/5."""
    rows = {
        'title': Text('Dungeon Progress', box(640, 227, 240, 30), .95),
        'floor': Text('Floor 1', box(497, 310), .92),
        'tag': Text('(HARD)', box(496, 332), .90),
        'count': Text('4/5', box(497, 344, 60, 26), .93),
        'next1': Text('Floor 2', box(574, 310), .90),
        'next2': Text('22/25', box(574, 344, 70, 26), .90),
        'next3': Text('Floor 3', box(650, 310), .90),
        'next4': Text('23/25', box(650, 344, 70, 26), .90),
    }
    rows.update(overrides)
    return [value for value in rows.values() if value is not None]


def test_the_live_panel_reads_floor_one_hard_at_four_of_five():
    payload = dungeon_progress(panel(), SIZE)

    assert payload['floor'] == 1
    assert payload['difficulty'] == 'HARD'
    assert (payload['steps'], payload['of']) == (4, 5)
    assert 'reason' not in payload
    assert steps_left(payload) == 1


def test_the_unvisited_floors_level_pair_is_never_mistaken_for_progress():
    """Floors 2 and 3 print 22/25 and 23/25 under their names.

    Anchoring on the first fraction on screen would report the party as 22 steps
    into a floor it has not entered, which is why the tag is the anchor.
    """
    payload = dungeon_progress(panel(tag=Text('(HARD)', box(650, 332), .90)), SIZE)

    assert payload['steps'] in (22, 23)
    assert payload['steps'] != 4
    # ... and the same panel read at its true column stays floor 1.
    assert dungeon_progress(panel(), SIZE)['floor'] == 1


def test_a_panel_with_its_count_missed_says_so_instead_of_guessing():
    payload = dungeon_progress(panel(count=None), SIZE)

    assert payload['steps'] is None
    assert payload['reason'] == (
        'the_floor_tag_is_on_screen_but_its_step_count_was_not_read')
    assert steps_left(payload) is None


def test_a_count_larger_than_its_own_floor_is_refused():
    payload = dungeon_progress(panel(count=Text('7/5', box(497, 344, 60, 26), .93)), SIZE)

    assert payload['steps'] is None and payload['of'] is None
    assert payload['reason'] == (
        'the_step_count_is_not_a_count_within_its_own_floor')


def test_no_panel_is_not_a_panel_that_failed_to_read():
    assert dungeon_progress([Text('Exploring Floor 1', box(140, 96), .9)], SIZE) is None
    assert steps_left(None) is None
