"""Tests for ``window.STEP_ROWS``: one shape is one row, and the row keeps its facts.

Twenty-seven branches of ``_plan_step`` were the same four statements transcribed
twenty-seven times -- look the page's one control up, refuse by name when it is not
bound, otherwise send it and name the pages that may follow.  D47 made them rows.
These tests hold the three things the transcription had and the table must not lose:

* the row answers the way the branch did (refusal, target, expectation, advance);
* the row is registered where the rest of the loop looks it up (``pages.PAGES``,
  ``pages.REFUSALS``, the fact record);
* a page may be answered in exactly one place -- a row or a branch, never both, so
  the drift gate can never be satisfied by two disagreeing answers.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import maalimbus.pages as pages  # noqa: E402
import maalimbus.window as window  # noqa: E402
from maalimbus.window import (ANY, CLICK, NODE, STEP_ROWS, plan_step)  # noqa: E402

BOX = [1668, 780, 124, 63]


def _chain_pages(source=None):
    """Pages still answered by a literal ``if page == 'X':`` branch."""
    if source is None:
        source = (ROOT / 'src' / 'maalimbus' / 'window.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == '_plan_step')
    found = set()
    for node in ast.walk(function):
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)):
            continue
        test = node.test
        if getattr(test.left, 'id', None) != 'page' or len(test.comparators) != 1:
            continue
        value = test.comparators[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            found.add(value.value)
    return found


def test_the_table_covers_only_pages_the_loop_knows():
    unknown = sorted(set(STEP_ROWS) - set(pages.PAGES))
    assert unknown == []


def test_every_row_refuses_with_a_reason_the_loop_can_classify():
    missing = sorted({row['refusal'] for row in STEP_ROWS.values()}
                     - set(pages.REFUSALS))
    assert missing == []


def test_every_row_expects_pages_that_exist():
    stray = sorted({(page, name) for page, row in STEP_ROWS.items()
                    for name in row['expect']
                    if name != ANY and name not in pages.PAGES})
    assert stray == []


def test_a_page_is_answered_in_exactly_one_place():
    overlap = sorted(set(STEP_ROWS) & _chain_pages())
    assert overlap == []


def test_every_page_the_chain_answers_is_in_the_fact_record():
    assert set(STEP_ROWS) | _chain_pages() == set(pages.DISPATCH_FACTS)


def test_a_missing_control_is_refused_by_the_rows_own_name():
    for page, row in STEP_ROWS.items():
        # A row that asks the node map for its box gets ``PAGE_NODES`` by default, so
        # its refusal is reachable only when the caller says that node is gone.
        nodes = {'DRIVE': None} if row.get('source') == 'nodes' else {}
        plan = plan_step(page, nodes=nodes)
        assert plan['action'] == window.RECORD, page
        assert plan['reason'] == row['refusal'], page


def test_a_bound_control_sends_that_box_and_the_rows_expectation():
    for page, row in STEP_ROWS.items():
        bound = {name: BOX for name in (row['control'], *row.get('also', ()))}
        nodes = {'DRIVE': BOX} if row.get('source') == 'nodes' else {}
        plan = plan_step(page, controls=bound, nodes=nodes)
        assert plan['reason'] == row['reason'], page
        assert plan['expect'] == list(row['expect']), page
        assert plan['advance'] is bool(row.get('advance')), page
        if row.get('source') == 'nodes':
            assert plan['action'] == NODE and plan['node'] == BOX, page
            assert plan['target'] is None, page
        else:
            assert plan['action'] == CLICK and plan['target'] == BOX, page


def test_a_fallback_control_is_used_only_when_the_first_is_missing():
    page = 'DEPLOYMENT'
    row = STEP_ROWS[page]
    assert row['also'], 'this test is only meaningful for a row with a fallback'
    first, second = row['control'], row['also'][0]
    assert plan_step(page, controls={second: BOX})['target'] == BOX
    both = plan_step(page, controls={first: [1, 2, 3, 4], second: BOX})
    assert both['target'] == [1, 2, 3, 4]


def test_the_menu_node_is_registered_by_default_and_reachable_when_it_is_not():
    assert plan_step('DRIVE')['node'] == 'MirrorDrive'
    plan = plan_step('DRIVE', nodes={'DRIVE': None})
    assert plan['action'] == window.RECORD
    assert plan['reason'] == 'mirror_menu_node_not_registered'


def test_a_row_cannot_name_a_forbidden_control():
    """The forbidden-control rule is checked after the row, on the plan it returns."""
    for name in window.FORBIDDEN_CONTROLS:
        for page, row in STEP_ROWS.items():
            if row['control'] != name:
                continue
            plan = plan_step(page, controls={name: BOX})
            assert plan['action'] == window.RECORD, (page, name)
            assert plan['reason'] == 'control_is_forbidden', (page, name)


def test_a_row_without_a_refusal_is_not_a_row():
    row = {'control': 'home.drive_button', 'expect': (ANY,), 'reason': 'x'}
    with pytest.raises(KeyError):
        window._row_step('HOME', row, controls={}, nodes={})
