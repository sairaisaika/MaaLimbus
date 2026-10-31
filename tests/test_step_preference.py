"""谁排最前：一张表说了算，不是三个 if 抢。"""
from __future__ import annotations

import maalimbus.runner as runner


def test_the_table_prefers_the_head_marker():
    record = {'map_train_next': {'box': [1, 2, 190, 190]},
              'map_edge_only': {'edge': [300, 2, 190, 190]}}
    assert runner.step_preference(record) == ('train_next', [1, 2, 190, 190])


def test_the_arrow_is_second():
    record = {'map_edge_only': {'edge': [300, 2, 190, 190]},
              'map_edge_step': {'step': [600, 600, 190, 190]}}
    assert runner.step_preference(record) == ('edge', [300, 2, 190, 190])


def test_the_line_is_third():
    record = {'map_edge_step': {'step': [600, 600, 190, 190]}}
    assert runner.step_preference(record) == ('line', [600, 600, 190, 190])


def test_nothing_present_means_no_lead():
    assert runner.step_preference({}) == (None, None)


def test_the_order_of_the_table_is_pinned():
    assert runner.STEP_PRIORITY == ('train_next', 'edge', 'line', 'adjacent')
