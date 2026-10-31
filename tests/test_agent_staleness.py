from __future__ import annotations
import importlib.util, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]

def _tool():
    spec = importlib.util.spec_from_file_location('run_mirror_once', REPO / 'tools' / 'run_mirror_once.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def test_an_older_agent_is_stale():
    assert _tool().agent_is_stale(head_time=200, agent_time=100) is True

def test_a_fresh_agent_is_not():
    assert _tool().agent_is_stale(head_time=100, agent_time=200) is False

def test_unknown_times_are_not_accused():
    assert _tool().agent_is_stale(None, 100) is False
    assert _tool().agent_is_stale(100, None) is False
