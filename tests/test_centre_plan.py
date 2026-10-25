"""A centred view is a loop on a measurement, not a fixed number of drags."""
from maalimbus.runner import centre_plan

SIZE = (1920, 1080)


def test_a_party_right_of_centre_asks_for_a_leftward_drag_of_the_finger():
    assert centre_plan((1400, 540), SIZE) == (-440, 0)


def test_a_party_too_high_asks_to_be_pushed_down():
    assert centre_plan((960, 400), SIZE) == (0, 140)


def test_a_centred_party_asks_for_nothing():
    assert centre_plan((960, 540), SIZE) is None
    assert centre_plan((965, 545), SIZE) is None


def test_the_tolerance_is_the_only_reason_a_small_offset_is_accepted():
    assert centre_plan((960, 548), SIZE) is None
    assert centre_plan((960, 548), SIZE, tolerance=4) == (0, -8)
    assert centre_plan((960, 551), SIZE) == (0, -11)


def test_a_frame_without_a_party_has_no_plan():
    assert centre_plan(None, SIZE) is None
    assert centre_plan((960, 540), None) is None
