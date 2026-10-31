"""一键运行入口：摘要要说人话，选设备要挑模拟器。"""
from __future__ import annotations

import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        'run_mirror_once', REPO / 'tools' / 'run_mirror_once.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_passing_run_says_through_and_lists_floors():
    tool = _tool()
    text = tool.summarise({'passed': True, 'events': 42, 'floors': [1, 2, 3], 'stop': 'done'}, 'D:/x')
    assert '通过' in text and '42' in text and '[1, 2, 3]' in text and 'D:/x' in text


def test_a_run_that_never_left_the_menu_says_so():
    tool = _tool()
    text = tool.summarise({'passed': False, 'events': 3, 'floors': [], 'stop': 'the_task_raised'}, None)
    assert '未通过' in text and '没进楼层' in text and 'the_task_raised' in text


def test_an_empty_result_points_at_the_log():
    tool = _tool()
    assert 'run-once.log' in tool.summarise({}, None)


def test_the_emulator_beats_a_physical_phone(monkeypatch):
    tool = _tool()
    monkeypatch.setattr(tool, 'devices', lambda: ['2G0YC5ZGCD03H6', '127.0.0.1:16416'])
    assert tool.pick_device() == '127.0.0.1:16416'


def test_an_explicit_address_wins(monkeypatch):
    tool = _tool()
    monkeypatch.setattr(tool, 'devices', lambda: ['127.0.0.1:16416'])
    assert tool.pick_device('emulator-5554') == 'emulator-5554'


def test_no_device_is_answered_with_none(monkeypatch):
    tool = _tool()
    monkeypatch.setattr(tool, 'devices', lambda: [])
    assert tool.pick_device() is None
