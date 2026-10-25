"""Every `map_vision.<name>` the runner calls must exist.

D306 wired `runner.candidates_of` to `map_vision.nearest_centre` while the function itself
was lost in a single-file rollback, so the branch raised `AttributeError` the first time it
ran.  A static check is cheaper than a live run to discover that.
"""

import ast
import pathlib

from maalimbus import map_vision

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _map_vision_names():
    tree = ast.parse((ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == 'map_vision'):
            names.add(node.attr)
    return names


def test_every_map_vision_name_the_runner_uses_exists():
    missing = sorted(n for n in _map_vision_names() if not hasattr(map_vision, n))
    assert missing == []


def test_the_check_can_fail():
    assert 'a_name_that_does_not_exist' not in dir(map_vision)
