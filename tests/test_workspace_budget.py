"""工作区预算：2 GiB 上限，超了要能自动收回，且不许删运行必需的东西。"""
from __future__ import annotations

import pathlib

from maalimbus import workspace


def _fake_tree(root: pathlib.Path) -> None:
    (root / 'build' / 'mxu-probe-271').mkdir(parents=True)
    (root / 'build' / 'mxu-probe-271' / 'maafw').write_bytes(b'x' * 100)
    (root / 'build' / 'startup-candidate-abc').mkdir()
    (root / 'build' / 'startup-candidate-abc' / 'blob').write_bytes(b'x' * 4096)
    (root / 'dist' / 'MaaLimbus').mkdir(parents=True)
    (root / 'dist' / 'MaaLimbus' / 'MaaLimbus.exe').write_bytes(b'x' * 1024)
    for index in range(3):
        (root / 'dist' / f'MaaLimbus.backup-{index}').mkdir()
        (root / 'dist' / f'MaaLimbus.backup-{index}' / 'blob').write_bytes(b'x' * 2048)
    runtime = root / 'evidence' / 'runtime'
    for index in range(7):
        run = runtime / f'run-{index}'
        run.mkdir(parents=True)
        for frame in range(5):
            (run / f'frame-{frame}.png').write_bytes(b'x' * 1024)
        (run / 'events.jsonl').write_text('{}\n', encoding='utf-8')


def test_the_probe_and_the_app_are_never_candidates(tmp_path):
    _fake_tree(tmp_path)
    names = {pathlib.Path(p).name for p in workspace.candidates(tmp_path)}
    assert 'mxu-probe-271' not in names
    assert 'MaaLimbus' not in names
    assert 'startup-candidate-abc' in names


def test_old_runs_are_candidates_and_the_newest_stay(tmp_path):
    _fake_tree(tmp_path)
    names = {pathlib.Path(p).name for p in workspace.candidates(tmp_path)}
    assert 'run-0' in names and 'run-1' in names
    assert 'run-6' not in names and 'run-5' not in names


def test_trim_runs_keeps_five_runs_and_three_frames(tmp_path):
    _fake_tree(tmp_path)
    freed = workspace.trim_runs(tmp_path)
    assert freed > 0
    runs = sorted((tmp_path / 'evidence' / 'runtime').glob('run-*'))
    for run in runs[-5:]:
        assert len(list(run.glob('frame-*.png'))) == 3
        assert (run / 'events.jsonl').is_file()
    # 旧 run 由 candidates() 负责整目录删除，裁剪只管帧
    assert {pathlib.Path(p).name for p in workspace.candidates(tmp_path)} >= {'run-0', 'run-1'}


def test_agent_backups_keep_only_the_newest(tmp_path):
    _fake_tree(tmp_path)
    agents = tmp_path / 'dist' / 'MaaLimbus'
    for index in range(3):
        folder = agents / f'agent.backup-{index}'
        folder.mkdir()
        (folder / 'blob').write_bytes(b'x' * 4096)
    names = {pathlib.Path(p).name for p in workspace.candidates(tmp_path)}
    assert {'agent.backup-0', 'agent.backup-1'} <= names
    assert 'agent.backup-2' not in names


def test_prune_stops_once_inside_the_budget(tmp_path):
    _fake_tree(tmp_path)
    out = workspace.prune(tmp_path, budget=1024)
    assert out['after'] < out['before']
    assert out['freed'] > 0
    assert (tmp_path / 'build' / 'mxu-probe-271' / 'maafw').is_file()


def test_a_dry_run_changes_nothing(tmp_path, capsys, monkeypatch):
    _fake_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert workspace.main([]) == 0
    assert '预演' in capsys.readouterr().out
    assert (tmp_path / 'build' / 'startup-candidate-abc').is_dir()


def test_apply_reports_what_it_freed(tmp_path, capsys, monkeypatch):
    _fake_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert workspace.main(['--apply', '--budget-gib', '0.001']) == 0
    out = capsys.readouterr().out
    assert '清理前' in out and 'GiB' in out
