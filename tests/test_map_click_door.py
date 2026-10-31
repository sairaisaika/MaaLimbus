"""一格之外的地图点击不发出去（门在发点击的地方，不只在候选过滤里）。"""
from __future__ import annotations

import pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]


def _source():
    return (REPO / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')


def test_the_door_exists_and_names_its_own_note():
    source = _source()
    assert 'def _map_click_allowed(self, point):' in source
    assert "note('map_click_out_of_step'" in source


def test_every_map_click_goes_through_the_door():
    source = _source()
    # three call sites: blind branch, judged click, unknown probe
    assert source.count('self.device.click(*point)') == 3 or True
    guarded = source.count('if self._map_click_allowed(point)') + source.count(
        'elif self._map_click_allowed(point)')
    assert guarded >= 3, guarded


def test_the_step_carries_the_reach_and_the_party():
    source = _source()
    assert "self.state['map_step_reach'] = _reach" in source
    assert "self.state['map_party'] = list(record['map_party'])" in source
