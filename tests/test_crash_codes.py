"""A native death must be a named end, not an absent one."""

from maalimbus import crash_codes


def test_a_fail_fast_is_named_as_a_crash_inside_a_click():
    assert crash_codes.name_for(3221226505) == 'the_controller_crashed_inside_a_click'


def test_the_same_value_as_a_python_negative_wraps_to_the_same_name():
    assert crash_codes.name_for(3221226505 - 2 ** 32) == 'the_controller_crashed_inside_a_click'


def test_an_ordinary_timeout_stays_unnamed():
    # A clean exit and a None must not be dressed up as a cause.
    assert crash_codes.name_for(0) is None
    assert crash_codes.name_for(None) is None
    assert crash_codes.name_for('nonsense') is None


def test_an_unknown_nonzero_code_is_not_invented():
    assert crash_codes.name_for(1) is None
