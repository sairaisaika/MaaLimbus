"""dist 备份清理：预演安全、保留最新几份、报告可回收空间。"""
from __future__ import annotations

import importlib.util
import os
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        'clean_dist_backups', REPO / 'tools' / 'clean_dist_backups.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make(base: pathlib.Path, names, size=1024):
    made = []
    for index, name in enumerate(names):
        folder = base / name
        folder.mkdir(parents=True)
        (folder / 'blob.bin').write_bytes(b'x' * size)
        os.utime(folder, (1000 + index, 1000 + index))
        made.append(folder)
    return made


def test_the_newest_three_stay_and_the_rest_go(tmp_path):
    tool = _tool()
    made = _make(tmp_path, [f'agent.backup-{i}' for i in range(5)])
    kept, doomed = tool.plan(made, 3)
    assert [p.name for p in kept] == ['agent.backup-4', 'agent.backup-3', 'agent.backup-2']
    assert [p.name for p in doomed] == ['agent.backup-1', 'agent.backup-0']


def test_survey_reports_both_families(tmp_path, monkeypatch):
    tool = _tool()
    _make(tmp_path / 'MaaLimbus', [f'agent.backup-{i}' for i in range(4)])
    _make(tmp_path, [f'.maalimbus-launcher-{i}' for i in range(3)])
    monkeypatch.setattr(tool, 'DIST', tmp_path)
    rows = tool.survey(keep_agent=2, keep_launcher=1)
    assert [row['label'] for row in rows] == ['agent.backup', 'launcher']
    assert len(rows[0]['delete']) == 2 and len(rows[1]['delete']) == 2
    assert rows[0]['reclaim'] > 0


def test_the_report_says_how_much_space(tmp_path, monkeypatch):
    tool = _tool()
    _make(tmp_path / 'MaaLimbus', [f'agent.backup-{i}' for i in range(3)])
    monkeypatch.setattr(tool, 'DIST', tmp_path)
    text = tool.report(tool.survey(keep_agent=1, keep_launcher=1))
    assert 'GiB' in text and '预演' not in text


def test_a_dry_run_deletes_nothing(tmp_path, monkeypatch, capsys):
    tool = _tool()
    _make(tmp_path / 'MaaLimbus', [f'agent.backup-{i}' for i in range(3)])
    monkeypatch.setattr(tool, 'DIST', tmp_path)
    assert tool.main([]) == 0
    assert '预演' in capsys.readouterr().out
    assert len(list((tmp_path / 'MaaLimbus').glob('agent.backup-*'))) == 3


def test_apply_removes_only_the_reported_ones(tmp_path, monkeypatch):
    tool = _tool()
    _make(tmp_path / 'MaaLimbus', [f'agent.backup-{i}' for i in range(4)])
    monkeypatch.setattr(tool, 'DIST', tmp_path)
    assert tool.main(['--apply', '--keep-agent', '1']) == 0
    left = sorted(p.name for p in (tmp_path / 'MaaLimbus').glob('agent.backup-*'))
    assert left == ['agent.backup-3']
