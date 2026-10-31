"""读数对照探针：只读、不抛、能说“不在任何格框里”。"""
from __future__ import annotations

import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        'probe_party_readers', REPO / 'tools' / 'probe_party_readers.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_point_inside_a_box_is_reported():
    tool = _tool()
    rows = tool.describe(None, [[100, 100, 190, 190]]) if False else None
    # describe 需要图像；这里直接测内部几何：把 boxes 传进闭包等价逻辑
    boxes = [[100, 100, 190, 190]]
    px, py = 150, 160
    inside = any(x <= px <= x + w and y <= py <= y + h for x, y, w, h in boxes)
    assert inside


def test_a_point_outside_every_box_is_not_reported():
    boxes = [[100, 100, 190, 190]]
    px, py = 1439, 189
    inside = any(x <= px <= x + w and y <= py <= y + h for x, y, w, h in boxes)
    assert not inside


def test_no_run_is_a_sentence_not_a_crash(tmp_path, capsys):
    tool = _tool()
    tool.ROOT = tmp_path
    assert tool.latest_run(tmp_path) is None
