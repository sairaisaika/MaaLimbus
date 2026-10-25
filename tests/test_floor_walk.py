"""A hop is measured from two node clicks, and never invented (D201)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]

import audit_floor_walk as walk  # noqa: E402


def _intent(stamp):
    return dict(event='window_intent', reason='map_node_click_is_the_only_proven_forward_input',
                utc=stamp, point=[10, 20])


def _seen(floor, stamp='2026-10-25T00:00:00Z'):
    return dict(event='map_observed', scene='MAP', floor=floor, utc=stamp)


def test_two_hops_have_one_gap():
    rows = [_seen(5), _intent('2026-10-25T00:00:00Z'), _intent('2026-10-25T00:00:15Z')]
    found = walk.walk(rows)
    assert found['hops'] == 2 and found['gaps'] == [15.0]
    assert found['floors'] == {'5': 2}


def test_one_hop_has_no_gap():
    found = walk.walk([_seen(1), _intent('2026-10-25T00:00:00Z')])
    assert found['hops'] == 1 and found['gaps'] == []


def test_a_non_node_input_is_not_a_hop():
    rows = [dict(event='window_intent', reason='win_rate_is_the_proven_auto_assign_control',
                 utc='2026-10-25T00:00:00Z')]
    assert walk.walk(rows)['hops'] == 0


def test_an_unreadable_floor_does_not_break_the_run():
    rows = [_seen(None), _intent('2026-10-25T00:00:00Z'), _intent('2026-10-25T00:00:05Z')]
    found = walk.walk(rows)
    assert found['hops'] == 2 and found['floors'] == {None: 2}


def test_a_corpus_without_a_hop_reports_no_cost():
    rows = [_seen(2)]
    rows.append(dict(event='mirror_loop_stopped', stop_path='agent_loop'))
    data = walk.report(pathlib.Path('build/none-such-corpus'))
    assert data['runs'] == 0 and data['hop_seconds'] is None
