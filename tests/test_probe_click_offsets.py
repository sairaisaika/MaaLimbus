from __future__ import annotations
import importlib.util, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]

def _tool():
    spec = importlib.util.spec_from_file_location('probe_click_offsets', REPO / 'tools' / 'probe_click_offsets.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def test_a_diagonal_half_step_is_one_step():
    row = _tool().offset((575, 335), (671, 230), step=190)
    assert row['dx'] == 96 and row['dy'] == -105 and row['in_one_step'] is True

def test_two_boxes_away_is_not():
    assert _tool().offset((575, 335), (288, 230), step=190)['in_one_step'] is False

def test_a_missing_party_or_point_gives_no_row():
    assert _tool().offset(None, (1, 2), step=190) is None
    assert _tool().offset((1, 2), None, step=190) is None

def test_rows_fall_back_to_the_box_centre_lifted_to_the_hexagon():
    events = [{'event': 'map_click_result', 'outcome': 'accepted',
               'party': [576, 335], 'target': [576, 169, 190, 190]}]
    rows = _tool().rows_from(events)
    assert rows[0]['dx'] == 95 and rows[0]['dy'] == (230 - 335)
