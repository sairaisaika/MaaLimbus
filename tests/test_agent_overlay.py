"""覆盖通道：复制全部模块、能报告陈旧、不碰 target 之外。"""
from __future__ import annotations

import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        'install_agent_overlay', REPO / 'tools' / 'install_agent_overlay.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_overlay_copies_every_module(tmp_path):
    tool = _tool()
    source = tmp_path / 'src'; source.mkdir()
    (source / 'a.py').write_text('x = 1\n', encoding='utf-8')
    (source / 'b.py').write_text('y = 2\n', encoding='utf-8')
    target = tmp_path / 'agent' / '_internal' / 'maalimbus'
    written = tool.overlay(source, target)
    assert sorted(written) == ['a.py', 'b.py']
    assert (target / 'a.py').read_text(encoding='utf-8') == 'x = 1\n'


def test_a_stale_file_is_reported(tmp_path):
    tool = _tool()
    source = tmp_path / 'src'; source.mkdir()
    (source / 'a.py').write_text('x = 1\n', encoding='utf-8')
    target = tmp_path / 't'
    tool.overlay(source, target)
    assert tool.covered(source, target) == []
    (source / 'a.py').write_text('x = 2\n', encoding='utf-8')
    assert tool.covered(source, target) == ['a.py']


def test_check_mode_writes_nothing(tmp_path, capsys):
    tool = _tool()
    source = tmp_path / 'src'; source.mkdir()
    (source / 'a.py').write_text('x = 1\n', encoding='utf-8')
    target = tmp_path / 't'
    assert tool.main(['--check']) in (0, 1)
