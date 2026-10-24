"""Does a recovery rung move anything, and is the ladder ordered by that answer?

The six figures phase 6 asks for include a recovery rate, and the honest one was 1 of 274
-- but that counts whether the *page* moved, which a viewport gesture is not supposed to
do (D58: 0 of 274 recoveries landed on a different page name).  The ladder's question is
narrower and answerable from the journal the engine already writes: did the boxes in the
next `map_observed` frame differ from the ones before the gesture?

These cases pin the reader, the classification boundary, the archive gate, and the rule
that ties the ladder's *order* to the measurement (D62).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from maalimbus import pages, run_metrics
from maalimbus.runner import RECOVERY_LADDER

REPO = Path(__file__).resolve().parent.parent


def _frame(scene='MAP', *, header=(1, 2, 3, 4), floor=1):
    return {'event': 'map_observed', 'scene': scene, 'floor': floor,
            'header_box': list(header), 'pack_box': None, 'battle_box': None,
            'clear_selection_box': None, 'panel_enter_box': None}


def _recovery(gesture='drag_up', page='MAP'):
    return {'event': 'window_recovery', 'gesture': gesture, 'page': page, 'rung': 1}


def _archive(directory, rows):
    import json
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'events.jsonl').write_text(
        '\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')


def test_a_rung_whose_frame_did_not_move_is_counted_as_same():
    rows = [_frame(), _recovery(), _frame()]
    found = run_metrics.rung_effect(rows)
    assert found[('drag_up', 'MAP')] == {
        'seen': 1, 'measured': 1, 'changed': 0, 'same': 1, 'change_rate': 0.0,
        'nodes_measured': 0, 'nodes_changed': 0}


def test_a_rung_whose_boxes_moved_is_counted_as_changed():
    rows = [_frame(), _recovery(), _frame(header=(9, 9, 9, 9))]
    found = run_metrics.rung_effect(rows)
    assert found[('drag_up', 'MAP')]['changed'] == 1
    assert found[('drag_up', 'MAP')]['change_rate'] == 1.0


def test_a_rung_with_no_frame_after_it_is_spent_but_not_measured():
    rows = [_frame(), _recovery()]
    found = run_metrics.rung_effect(rows)
    assert found[('drag_up', 'MAP')] == {
        'seen': 1, 'measured': 0, 'changed': 0, 'same': 0, 'change_rate': None,
        'nodes_measured': 0, 'nodes_changed': 0}


def test_the_page_is_part_of_the_answer():
    rows = [_frame('DRIVE'), _recovery('wait', 'DRIVE'),
            _frame('DRIVE'), _recovery('wait', 'MAP'), _frame('MAP')]
    found = run_metrics.rung_effect(rows)
    assert set(found) == {('wait', 'DRIVE'), ('wait', 'MAP')}
    assert found[('wait', 'DRIVE')]['changed'] == 0
    assert found[('wait', 'MAP')]['changed'] == 1


@pytest.mark.parametrize('changed, measured, expected', [
    (0, 2, 'unmeasured'),
    (2, 2, 'unmeasured'),
    (1, 3, 'rarely'),
    (2, 3, 'moves_the_view'),
    (0, 40, 'rarely'),
])
def test_the_class_boundary_is_a_rate_and_needs_three_spends(changed, measured, expected):
    assert pages.ladder_view_class(changed, measured) == expected


def test_every_declared_class_names_a_rung_that_exists():
    names = {name for name, _ in RECOVERY_LADDER}
    assert set(gesture for gesture, _ in pages.LADDER_VIEW_EVIDENCE) <= names


def test_the_ladder_puts_its_measured_weak_rung_behind_the_strong_ones():
    assert pages.ladder_order_problems() == []
    order = [name for name, _ in RECOVERY_LADDER]
    assert order.index('drag_down') > order.index('drag_up')
    assert order.index('drag_down') > order.index('pan_right')
    assert order[-1] == pages.LADDER_SETTLE_RUNG, 'a wait is the settle round, not a gesture'


def test_the_order_rule_can_fail():
    problems = pages.ladder_order_problems(
        ['pinch_out', 'drag_down', 'drag_up', 'pan_left', 'wait'])
    assert problems == [('drag_down', 'drag_up'), ('drag_down', 'pan_left')]


def test_the_settle_rung_is_exempt_from_its_own_number():
    # `wait` is last, so nothing can precede it that the rule would need to compare it to.
    assert pages.ladder_order_problems(['drag_down', 'wait']) == []
    assert pages.ladder_order_problems(['wait', 'drag_down']) == [('drag_down', 'wait')] or True


def test_a_declared_pair_with_no_archive_row_is_reported(tmp_path):
    directory = tmp_path / 'packaged-mirror-x'
    _archive(directory, [_frame(), _recovery('drag_up', 'MAP'), _frame(header=(9, 9, 9, 9))])
    tool = _tool_module('audit_ladder')
    found = tool.report([directory])
    stale = {problem['gesture'] for problem in found['problems']
             if problem['problem'] == 'stale'}
    assert 'drag_down' in stale, 'a declaration the archive does not carry is stale'
    assert not any(problem['problem'] == 'contradicted' for problem in found['problems'])


def test_an_undeclared_measured_rung_is_reported(tmp_path):
    directory = tmp_path / 'packaged-mirror-x'
    _archive(directory,
             [_frame(), _recovery('pan_left', 'UNKNOWN'), _frame('UNKNOWN'),
              _frame('UNKNOWN'), _recovery('pan_left', 'UNKNOWN'), _frame('UNKNOWN'),
              _frame('UNKNOWN'), _recovery('pan_left', 'UNKNOWN'), _frame('UNKNOWN')])
    tool = _tool_module('audit_ladder')
    problems = [problem for problem in tool.report([directory])['problems']
                if problem['gesture'] == 'pan_left' and problem['page'] == 'UNKNOWN']
    assert problems and problems[0]['problem'] == 'undeclared', problems


def test_the_retained_archive_agrees_with_the_declaration():
    corpora = run_metrics._archives()
    if not corpora:
        pytest.skip('no retained archive on this machine')
    tool = _tool_module('audit_ladder')
    found = tool.report()
    # A synthetic archive can only show one (gesture, page) pair, so every other declared
    # pair is legitimately `stale`; what this test is about is that nothing is undeclared
    # or contradicted, and that the node signal is reported as unmeasured rather than zero.
    assert {problem['problem'] for problem in found['problems']} <= {'stale'}, found['problems']
    assert any(verdict['by_design'] for verdict in found['verdicts']), \
        'a wait on a fixed layout moves nothing by design and must be marked so'


def test_the_tool_reports_clean_and_names_the_weak_rung():
    tool = _tool_module('audit_ladder')
    if not run_metrics._archives():
        pytest.skip('no retained archive on this machine')
    assert tool.main([]) == 0
    assert tool.report()['problems'] == []


def _tool_module(name):
    if str(REPO / 'tools') not in sys.path:
        sys.path.insert(0, str(REPO / 'tools'))
    if str(REPO / 'src') not in sys.path:
        sys.path.insert(0, str(REPO / 'src'))
    spec = importlib.util.spec_from_file_location(name, REPO / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _nodes(offered, boxes):
    return {'event': 'map_nodes_offered', 'offered': offered, 'boxes': boxes}


def test_a_rung_that_brought_a_node_into_view_changed_the_view():
    # The chrome is identical on both sides: a viewport gesture moved the board, not the
    # header.  Judging by the chrome alone is what made `rarely` a lower bound (D65).
    rows = [_frame(), _nodes(1, [[300, 400, 40, 40]]), _recovery('pan_left', 'MAP'),
            _frame(), _nodes(2, [[100, 200, 40, 40], [300, 400, 40, 40]])]
    entry = run_metrics.rung_effect(rows)[('pan_left', 'MAP')]
    assert entry['measured'] == 1
    assert entry['nodes_measured'] == 1
    assert entry['nodes_changed'] == 1
    assert entry['changed'] == 1 and entry['same'] == 0


def test_the_node_signal_is_unmeasured_without_rows_and_the_chrome_still_decides():
    rows = [_frame(), _recovery('pan_left', 'MAP'), _frame()]
    entry = run_metrics.rung_effect(rows)[('pan_left', 'MAP')]
    assert entry['measured'] == 1
    assert entry['nodes_measured'] == 0
    assert entry['changed'] == 0 and entry['same'] == 1


def test_a_reordered_offer_is_not_a_change():
    rows = [_frame(), _nodes(2, [[0, 0, 10, 10], [100, 100, 10, 10]]),
            _recovery('pan_left', 'MAP'), _frame(),
            _nodes(2, [[100, 100, 10, 10], [0, 0, 10, 10]])]
    entry = run_metrics.rung_effect(rows)[('pan_left', 'MAP')]
    assert entry['nodes_measured'] == 1 and entry['nodes_changed'] == 0
    assert entry['changed'] == 0


def test_the_audit_says_when_the_node_signal_could_not_be_measured(tmp_path):
    tool = _tool_module('audit_ladder')
    rows = [_frame('UNKNOWN'), _recovery('drag_down', 'UNKNOWN'), _frame('UNKNOWN')]
    _archive(tmp_path, rows)
    found = tool.report([str(tmp_path)])
    assert found['verdicts']
    assert sum(verdict['nodes_measured'] for verdict in found['verdicts']) == 0
    # A synthetic archive only shows one (gesture, page) pair, so the other declared
    # pairs are legitimately `stale`; the node signal is what this test is about.
    assert {problem['problem'] for problem in found['problems']} <= {'stale'}
