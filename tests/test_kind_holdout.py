"""An order fitted on one half has to be checked on the other (D200)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]

import audit_kind_holdout as holdout  # noqa: E402


def _click(outcome, target=(10, 20, 30, 30)):
    return dict(event='map_click_result', outcome=outcome, target=list(target))


def _run(kind, outcomes, box=(10, 20, 30, 30)):
    rows = [dict(event='map_nodes_offered', boxes=[list(box)], kinds=[kind])]
    rows += [_click(outcome, box) for outcome in outcomes]
    rows.append(dict(event='mirror_loop_stopped', stop_path='agent_loop'))
    return rows


def test_a_kind_that_flips_between_halves_is_reported_as_drift():
    runs = [('a', _run('lit_icon', ['accepted'] * 4)),
            ('b', _run('lit_icon', ['rejected'] * 4))]
    halves = holdout.split(runs)
    rows = holdout.drift(halves)
    assert rows[0]['kind'] == 'lit_icon'
    assert rows[0]['stable'] is False


def test_a_kind_that_holds_its_rate_is_stable():
    runs = [('a', _run('gold_badge_node', ['accepted', 'rejected'])),
            ('b', _run('gold_badge_node', ['accepted', 'rejected']))]
    rows = holdout.drift(holdout.split(runs))
    assert rows[0]['stable'] is True


def test_a_kind_measured_in_one_half_only_is_not_compared():
    runs = [('a', _run('lit_icon', ['accepted'])),
            ('b', _run('gold_badge_node', ['accepted']))]
    rows = holdout.drift(holdout.split(runs))
    assert rows == []


def test_a_legacy_run_is_not_counted():
    legacy = _run('lit_icon', ['accepted'])
    legacy = [row for row in legacy if row['event'] != 'mirror_loop_stopped']
    assert holdout.by_kind([('legacy', legacy)]) == {}


def test_the_split_is_by_position_not_by_kind():
    runs = [('a', _run('lit_icon', ['accepted'])), ('b', _run('lit_icon', ['rejected']))]
    halves = holdout.split(runs)
    assert halves[holdout.EARLY]['lit_icon']['rate'] == 1.0
    assert halves[holdout.LATE]['lit_icon']['rate'] == 0.0
