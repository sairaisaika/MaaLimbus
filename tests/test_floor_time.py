"""Where the seconds inside a floor went (D122)."""
import json
import pathlib

import pytest

from maalimbus import run_metrics

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVE = ROOT / 'evidence/runtime/packaged-mirror-20261024-124531'


def _row(event, utc, **fields):
    return dict(fields, event=event, utc=utc)


def _stamp(seconds):
    return f'2026-10-24T02:{int(seconds) // 60:02d}:{int(seconds) % 60:02d}+00:00'


def _beat(seconds, page, floor=None):
    fields = {'page': page, 'phase': 'step_start'}
    if floor is not None:
        fields['floor'] = floor
    return _row('loop_heartbeat', _stamp(seconds), **fields)


def test_the_time_inside_a_floor_is_split_by_what_the_page_was():
    rows = [_beat(0, 'MAP', '3'), _beat(10, 'MAP', '3'), _beat(20, 'BATTLE_HUD', '3'),
            _beat(60, 'BATTLE_HUD', '3'), _beat(70, 'SHOP', '3'), _beat(80, 'MAP', '3')]
    entry = run_metrics.floor_time(rows)[3]
    assert entry['groups']['map']['seconds'] == 20.0
    assert entry['groups']['battle']['seconds'] == 50.0
    assert entry['groups']['shop']['seconds'] == 10.0
    assert entry['groups']['battle']['share'] == 0.625


def test_a_gap_before_any_floor_is_named_is_not_a_floor():
    rows = [_beat(0, 'MAP'), _beat(30, 'MAP'), _beat(40, 'MAP', '2'), _beat(50, 'MAP', '2')]
    floors = run_metrics.floor_time(rows)
    assert list(floors) == [2]
    assert floors[2]['seconds'] == 10.0


def test_a_gap_beyond_the_cap_is_not_attributed():
    rows = [_beat(0, 'MAP', '2'), _beat(600, 'MAP', '2')]
    # Nothing was attributed, so the floor is not invented with a zero.
    assert run_metrics.floor_time(rows) == {}


def test_the_nested_events_name_what_cost_the_time():
    rows = [_beat(0, 'MAP', '2'), _row('map_observed', _stamp(5), scene='MAP', floor='2'),
            _row('map_observed', _stamp(15), scene='MAP', floor='2'), _beat(20, 'MAP', '2')]
    entry = run_metrics.floor_time(rows)[2]
    # A gap belongs to the row that produced it: the opening beat 0 -> 5 s, the reads
    # 5 -> 15 s, and the closing beat owns nothing (it is the last row).
    assert entry['events']['loop_heartbeat']['seconds'] == 5.0
    assert entry['events']['map_observed']['seconds'] == 15.0


def test_an_unclassified_page_lands_in_other():
    assert run_metrics.floor_time_group('SOMETHING_NEW') == 'other'
    assert run_metrics.floor_time_group('BATTLE_HUD') == 'battle'
    assert run_metrics.floor_time_group('SHOP_PURCHASE') == 'shop'


def test_the_groups_cover_every_registered_page_once():
    from maalimbus import pages
    seen = {}
    for group, names in run_metrics.FLOOR_TIME_GROUPS:
        for name in names:
            assert name not in seen, f'{name} listed twice'
            seen[name] = group
            assert name in pages.PAGES, f'{name} is not a registered page'


def test_no_run_named_a_floor():
    assert run_metrics.floor_time([]) == {}
    assert run_metrics.floor_time([_beat(0, 'MAP')]) == {}


def test_the_retained_run_splits_into_map_battle_shop():
    if not (LIVE / 'events.jsonl').exists():
        pytest.skip('the retained run is not in this checkout')
    rows = [json.loads(line) for line in
            (LIVE / 'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    floors = run_metrics.floor_time(rows)
    assert floors, 'the run named its floor'
    entry = floors[max(floors)]
    assert entry['groups']['map']['seconds'] > entry['groups']['battle']['seconds'] > 0
    assert 0.95 <= sum(g['share'] for g in entry['groups'].values()) <= 1.01


def test_the_tool_reports_and_refuses(tmp_path, capsys):
    import importlib.util
    path = ROOT / 'tools/audit_floor_time.py'
    spec = importlib.util.spec_from_file_location('audit_floor_time', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(['--root', str(LIVE)]) == 0
    printed = capsys.readouterr().out
    assert 'floor 3:' in printed and 'battle' in printed
    empty = tmp_path / 'empty'
    empty.mkdir()
    assert module.main(['--root', str(empty)]) == 2
