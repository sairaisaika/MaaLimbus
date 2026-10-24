"""A killed verifier must not leave an agent holding the controller (D94).

The 2026-10-24 04:59 attempt was killed at its budget and left
`MaaLimbusAgent.exe` running with the controller lease. The next attempt wrote no
event at all for 481 s and read as a silent death: `subprocess.run(timeout=...)`
kills the direct child, and on Windows nothing travels down to the grandchild.

Two rules follow: an overrun kills the whole tree, and a new attempt first reaps
agents that a previous attempt left behind -- and says in its record that it did.
"""

import ast
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS = ROOT / 'tools' / 'selfrun_mirror.py'


def _harness():
    import importlib.util
    spec = importlib.util.spec_from_file_location('selfrun_mirror', HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_the_agent_image_is_reaped():
    harness = _harness()
    rows = [(10, 'python.exe'), (11, 'MaaLimbusAgent.exe'), (12, 'MuMuNxMain.exe'),
            (13, 'maalimbusagent.exe')]
    assert harness.agent_processes(lambda: rows) == [11, 13]


def test_every_agent_a_previous_attempt_left_is_killed():
    harness = _harness()
    killed = []
    found = harness.reap_stale_agents(list_processes=lambda: [(7, 'MaaLimbusAgent.exe'),
                                                              (9, 'MaaLimbusAgent.exe')],
                                      kill=lambda pid: killed.append(pid) or True)
    assert found == {'found': [7, 9], 'killed': [7, 9]}
    assert killed == [7, 9]


def test_a_kill_that_fails_is_reported_and_not_raised():
    harness = _harness()
    found = harness.reap_stale_agents(list_processes=lambda: [(7, 'MaaLimbusAgent.exe')],
                                      kill=lambda pid: False)
    assert found == {'found': [7], 'killed': []}


def test_nothing_to_reap_is_an_empty_answer():
    harness = _harness()
    assert harness.reap_stale_agents(list_processes=lambda: []) == {'found': [], 'killed': []}


def test_reap_asks_for_the_tree():
    """`taskkill /T` is the whole point: the agent is the verifier's child."""
    harness = _harness()
    calls = []
    monkey = harness.subprocess

    class Done:
        returncode = 0

    original = monkey.run
    monkey.run = lambda argv, **kw: calls.append(argv) or Done()
    try:
        assert harness._taskkill(4321) is True
    finally:
        monkey.run = original
    assert calls == [['taskkill', '/F', '/T', '/PID', '4321']]


def test_a_command_that_returns_is_not_a_kill():
    harness = _harness()
    done = harness.run_bounded([sys.executable, '-c', 'print("ok")'], cwd=str(ROOT), timeout=30)
    assert done['returncode'] == 0
    assert done['killed'] is False
    assert done['reaped'] is None
    assert 'ok' in done['stdout']


def test_an_overrun_kills_the_tree_and_still_hands_back_the_output():
    harness = _harness()
    asked = []
    done = harness.run_bounded([sys.executable, '-c', 'import time; time.sleep(20)'],
                               cwd=str(ROOT), timeout=0.4,
                               kill=lambda pid: asked.append(pid) or True, reap_seconds=5)
    assert done['returncode'] == 124
    assert done['killed'] is True
    assert done['reaped'] is True
    assert asked, 'the kill was never asked for'


def test_a_real_timeout_ends_in_seconds_rather_than_waiting_out_the_command():
    """The measured failure was 481 s of nothing; the kill must not wait for the sleep."""
    harness = _harness()
    import time
    started = time.monotonic()
    done = harness.run_bounded([sys.executable, '-c', 'import time; time.sleep(30)'],
                               cwd=str(ROOT), timeout=0.4,
                               kill=lambda pid: True, reap_seconds=5)
    assert done['killed'] is True
    assert time.monotonic() - started < 10


def test_the_attempt_reaps_before_it_runs_and_kills_the_tree_on_overrun():
    source = HARNESS.read_text(encoding='utf-8')
    tree = ast.parse(source)
    attempt = next(node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef) and node.name == 'attempt')
    names = {node.func.id for node in ast.walk(attempt)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert 'reap_stale_agents' in names, 'the attempt does not reap a stale agent'
    assert 'run_bounded' in names, 'the attempt does not go through the bounded runner'
    # and it must not hold the subprocess.run call that cannot kill the tree
    banned = [node for node in ast.walk(attempt)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr == 'run'
              and getattr(node.func.value, 'id', None) == 'subprocess']
    assert not banned, 'subprocess.run(timeout=...) came back into the attempt'


def test_the_record_names_the_reap_and_the_kill():
    source = HARNESS.read_text(encoding='utf-8')
    assert "record['stale_agents'] = reap_stale_agents()" in source
    assert "record['reaped'] = finished.get('reaped')" in source


def test_importing_the_harness_does_not_touch_the_game():
    """The module must stay importable without an emulator or a device."""
    harness = _harness()
    assert harness.AGENT_IMAGE == 'MaaLimbusAgent.exe'
    assert harness.MARGIN_SECONDS >= 1
