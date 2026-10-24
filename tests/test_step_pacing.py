"""The pause between two steps is a spacing, not a sleep (D93).

Measured: a live battle turn is 12.6 s, of which about 2.5 s is the settle loop
reading an unchanged page after the click
(evidence/runtime/packaged-mirror-20261024-044536, rows 11-20). The loop then
slept the whole ``interval`` again, so the same spacing was paid twice. The rule
is that ``interval`` is measured from the input the loop sent, and whatever the
step already spent after that input is part of it.
"""

import ast
import pathlib
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'src' / 'maalimbus' / 'runner.py'


def _loop(now=100.0):
    """A loop that only carries the clock and the two fields the rule reads."""
    import maalimbus.runner as runner_module
    loop = runner_module.MirrorRunner.__new__(runner_module.MirrorRunner)
    loop.artifacts = {}
    loop._clock = now
    return loop


def _pause_with(monkeypatch, *, now, input_at, interval=4.0):
    import maalimbus.runner as runner_module

    monkeypatch.setattr(runner_module.time, 'monotonic', lambda: now)
    loop = _loop()
    if input_at is not None:
        loop.artifacts['input_at'] = input_at
    return loop._pause_between_steps(interval)


def test_a_loop_that_never_sent_an_input_pays_the_whole_pause(monkeypatch):
    assert _pause_with(monkeypatch, now=100.0, input_at=None) == 4.0


def test_the_settle_reads_after_the_input_are_part_of_the_pause(monkeypatch):
    # the click went out 2.6 s ago: the settle loop spent that watching the page
    import pytest
    assert _pause_with(monkeypatch, now=102.6, input_at=100.0) == pytest.approx(1.4)


def test_an_input_older_than_the_interval_needs_no_pause_at_all(monkeypatch):
    assert _pause_with(monkeypatch, now=105.0, input_at=100.0) == 0.0


def test_an_input_exactly_at_the_interval_needs_no_pause(monkeypatch):
    assert _pause_with(monkeypatch, now=104.0, input_at=100.0) == 0.0


def test_a_clock_that_went_backwards_does_not_shorten_the_pause(monkeypatch):
    # monotonic clock skew must not produce a negative pause and must not extend it
    assert _pause_with(monkeypatch, now=99.0, input_at=100.0) == 4.0


def test_the_interval_is_the_caller_s_number(monkeypatch):
    assert _pause_with(monkeypatch, now=101.0, input_at=100.0, interval=1.0) == 0.0
    assert _pause_with(monkeypatch, now=100.0, input_at=100.0, interval=1.0) == 1.0


def test_the_step_stamps_the_moment_the_input_left():
    source = RUNNER.read_text(encoding='utf-8')
    stamp = "self.artifacts['input_at'] = time.monotonic()"
    assert stamp in source
    # and it sits with a counter, right after an input went out
    marker = "self.artifacts['clicks_sent'] += 1"
    spots = [i for i in range(len(source)) if source.startswith(marker, i)]
    assert any(stamp in source[i:i + 320] for i in spots), 'no click site stamps its moment'


def test_the_loop_uses_the_rule_and_not_a_bare_sleep():
    """A bare `time.sleep(interval)` at the end of the walk is the regression."""
    source = RUNNER.read_text(encoding='utf-8')
    tree = ast.parse(source)
    walk = next(node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == '_walk')
    sleeps = [node for node in ast.walk(walk)
              if isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute) and node.func.attr == 'sleep']
    for call in sleeps:
        assert not (len(call.args) == 1 and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == 'interval'), \
            f'a bare time.sleep(interval) survived at line {call.lineno}'
    names = {node.attr for node in ast.walk(walk)
             if isinstance(node, ast.Attribute) and node.attr == '_pause_between_steps'}
    assert names, 'the walk no longer asks the rule for its pause'


def test_the_pause_is_zero_when_the_step_already_waited_long_enough(monkeypatch):
    loop = _loop()
    loop.artifacts['input_at'] = 100.0
    import maalimbus.runner as runner_module
    monkeypatch.setattr(runner_module.time, 'monotonic', lambda: 130.0)
    assert loop._pause_between_steps(4.0) == 0.0
    # and the loop would then skip the sleep entirely rather than sleeping 0
    assert not loop._pause_between_steps(4.0)
