"""桌面端启动诊断工具：只读、可离线跑、探针失败也不许抛。"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        'diagnose_desktop_launch', REPO / 'tools' / 'diagnose_desktop_launch.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_check_answers_a_row():
    tool = _tool()
    rows = tool.report()
    assert len(rows) == len(tool.CHECKS)
    names = [row[0] for row in rows]
    assert len(set(names)) == len(names)
    for name, status, detail in rows:
        assert status in (tool.OK, tool.WARN, tool.BLOCK)
        assert isinstance(detail, str) and detail


def test_a_probe_that_raises_becomes_a_value(monkeypatch):
    tool = _tool()

    def boom(*args, **kwargs):
        raise OSError('probe died')

    monkeypatch.setattr(tool.subprocess, 'run', boom)
    assert tool._ps('anything').startswith('probe_failed:')


def test_the_exit_code_says_whether_something_blocks(monkeypatch):
    tool = _tool()
    monkeypatch.setattr(tool, 'report', lambda: [('exe', tool.BLOCK, 'no exe')])
    assert tool.main([]) == 1
    monkeypatch.setattr(tool, 'report', lambda: [('exe', tool.WARN, 'unsigned')])
    assert tool.main([]) == 0


def test_the_tool_runs_against_this_checkout():
    """真实 checkout 上跑一次：结论要么 ok 要么 warn，不允许抛。"""
    done = subprocess.run(
        ['python', str(REPO / 'tools' / 'diagnose_desktop_launch.py')],
        capture_output=True, text=True, timeout=180)
    assert done.returncode in (0, 1), done.stderr[-400:]
    assert 'exe' in done.stdout and 'webview2' in done.stdout
