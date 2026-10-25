"""The map/panel structural question is measured, not assumed.

The tool exists so every future run thickens the sample; it must never claim separation
from an unbalanced survey (one panel frame is not a distribution).
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        'audit_page_structure', ROOT / 'tools' / 'audit_page_structure.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_range_reports_three_numbers_rounded():
    tool = _tool()
    assert tool._range([0.00104, 0.00449, 0.00199]) == (0.001, 0.002, 0.004)


def test_an_empty_group_says_so_instead_of_zero():
    tool = _tool()
    data = {'runs': 0, 'groups': {'MAP': [], 'NODE_PANEL': []}}
    lines = tool.report(data)
    assert lines[0] == 'runs read: 0'
    assert all('no frame whose picture was kept' in line for line in lines[1:])


def test_the_gap_is_named_only_when_both_groups_are_measured():
    tool = _tool()
    lines = tool.report({'runs': 1, 'groups': {'MAP': [(0.001, 40)], 'NODE_PANEL': []}})
    assert not any('gap' in line for line in lines)


def test_overlap_is_reported_as_not_separable():
    tool = _tool()
    lines = tool.report({'runs': 1, 'groups': {'MAP': [(0.010, 40)], 'NODE_PANEL': [(0.006, 50)]}})
    assert any('not separable' in line for line in lines)


def test_the_retained_archive_answers_or_refuses():
    """Either the archive holds both scenes (numbers printed) or it says so (exit 2)."""
    tool = _tool()
    data = tool.survey(limit=25)
    lines = tool.report(data)
    assert lines[0].startswith('runs read:')
    measured = [scene for scene, rows in data['groups'].items() if rows]
    assert measured or 'no frame' in ' '.join(lines)


def test_the_tool_runs_clean(capsys):
    tool = _tool()
    code = tool.main([])
    out = capsys.readouterr().out
    assert code in (0, 2)
    if code == 0:
        assert 'runs read:' in out
