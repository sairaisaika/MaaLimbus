"""车头外推的几何不变量（D413）。"""
from __future__ import annotations

from maalimbus import runner


def test_two_steps_away_is_where_the_formula_says():
    assert runner.train_distance_ok((1053, 456), (863, 456), 190)


def test_one_step_away_is_still_accepted():
    assert runner.train_distance_ok((1053, 456), (863, 456), 190) is True
    assert runner.train_distance_ok((863 + 190, 456), (863, 456), 190) is True


def test_the_live_miss_is_rejected():
    """-181512: party (863,456), extrapolation (293,796) -> 910 px on a 190 px step."""
    assert runner.train_distance_ok((293, 796), (863, 456), 190) is False


def test_without_a_step_nothing_is_rejected():
    assert runner.train_distance_ok((293, 796), (863, 456), 0) is True
    assert runner.train_distance_ok(None, (863, 456), 190) is True
    assert runner.train_distance_ok((293, 796), None, 190) is True
