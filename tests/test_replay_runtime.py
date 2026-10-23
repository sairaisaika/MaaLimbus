"""The replay layer must be provable by building one, not by counting the subclasses.

D52 moved sixteen controllers onto one layer and gated the change with a static
inventory: sixteen classes inheriting `ReplayController`, problems: none. That
gate was green while forty tools were broken, because the layer assigned
`self.uuid`, which Maa's `Controller` exposes as a read-only property: every
`ReplayController` raised `AttributeError: property 'uuid' of 'Replay' object has
no setter` the moment a tool built one (found 2026-10-23 by running
`tools/verify_city_gifts_replay.py`).

So this file proves the layer at runtime: it opens the Maa library, builds a real
`ReplayController`, and asserts the promise the static count could not -
that a retained frame yields a screenshot, that input is refused, and that a
scenario which names its input gets that one input recorded. The tool-side
imports are checked too: a tool that imports the layer has to put `src` on the
path itself, or it fails at import time in a fresh interpreter.
"""

import ast
import pathlib
import sys

import numpy as np
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))

from maalimbus.replay import (  # noqa: E402
    OFFLINE_UUID,
    ReplayController,
    ReplayFrames,
    ReplayInputRefused,
)


def _library_binary():
    for candidate in ('build/mxu-probe-271/maafw', 'dist/MaaLimbus/maafw'):
        path = REPO / candidate
        if path.exists():
            return path
    return None


@pytest.fixture(scope='module')
def library():
    binary = _library_binary()
    if binary is None:
        pytest.skip('no maafw binary to open')
    from maa.library import Library

    try:
        Library.open(binary.resolve(), agent_server=False)
    except Exception:  # already open in this process
        pass
    return binary


def _frame(value=1):
    return np.full((64, 64, 3), value, dtype=np.uint8)


def test_the_layer_can_be_built_as_a_controller(library):
    controller = ReplayController([_frame(3)])

    assert controller.request_uuid() == OFFLINE_UUID
    assert controller.connect() is True
    assert controller.disconnect() is True
    assert controller.get_features() == 0


def test_a_built_controller_shows_its_frame_and_refuses_input(library):
    controller = ReplayController([_frame(5)])

    shown = controller.screencap()
    assert shown.shape == (64, 64, 3) and int(shown[0][0][0]) == 5
    shown[:] = 0  # a copy, so the scenario's frame is unchanged
    assert int(controller.screencap()[0][0][0]) == 5

    with pytest.raises(ReplayInputRefused, match='click'):
        controller.click(10, 20)
    assert controller.inputs == []
    assert controller.attempts == [('click', 10, 20)]


def test_a_scenario_that_names_its_input_gets_that_one_recorded(library):
    seen = []

    def expects(kind, position, *args):
        seen.append((kind, position, args))
        return kind == 'swipe'

    controller = ReplayController([_frame()], expects=expects)

    assert controller.swipe(1, 2, 3, 4, 300) is True
    assert controller.inputs == [('swipe', 1, 2, 3, 4, 300)]
    with pytest.raises(ReplayInputRefused):
        controller.click(1, 2)
    assert seen[0][0] == 'swipe' and seen[1][0] == 'click'


def test_the_layer_never_assigns_the_base_class_read_only_uuid():
    source = (REPO / 'src' / 'maalimbus' / 'replay.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    assigned = [target.attr for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                for target in node.targets
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                and target.value.id == 'self']
    assert 'uuid' not in assigned, 'Controller.uuid is a read-only property'
    assert 'scenario_uuid' in assigned


def test_a_tool_that_imports_the_layer_puts_src_on_the_path_first():
    tools = REPO / 'tools'
    offenders = []
    for path in sorted(tools.glob('*.py')):
        source = path.read_text(encoding='utf-8')
        if 'from maalimbus.replay import' not in source and 'import maalimbus.replay' not in source:
            continue
        lines = source.splitlines()
        layer_line = next(i for i, line in enumerate(lines)
                          if 'maalimbus.replay' in line and (line.startswith('from') or line.startswith('import')))
        bootstrapped = any("path.insert(0, str" in line and 'src' in line for line in lines[:layer_line])
        if not bootstrapped:
            offenders.append(path.name)
    assert offenders == [], 'these tools cannot import the layer in a fresh interpreter'


def test_the_frames_half_needs_no_maa_library():
    # the promise is testable offline: this class carries no CustomController base
    assert not any(base.__name__ == 'CustomController' for base in ReplayFrames.__mro__)
    assert any(base.__name__ == 'CustomController' for base in ReplayController.__mro__)
