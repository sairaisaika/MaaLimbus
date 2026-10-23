"""Every native read in `src/maalimbus` goes through one door, and that door is bounded.

The bound (`runner.bounded_read`) is only worth anything if it is the *only* place a
pipeline node is started for a page read.  The defect it fixes came back twice from a
site somebody had not thought about: `7b91b6e` bounded the settle helper and left the
inline settle read unbounded; `dea7028` bounded `MirrorRunner._observe` and left
`MaaObserver.observe` -- the door `tools/lux_task.py`, `tools/reward_task.py` and the
window layer read through -- open.  This is the counter-example that stops a third one:
a new `run_node` call, or a new `observer.observe` call, has to be added to the
baselines below on purpose.

Scope is `src/maalimbus` (the product).  `tools/` holds one-shot diagnostics that pass
their own deadlines; they are named here so a reader knows they exist rather than being
silently trusted.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "maalimbus"

# file -> sorted `enclosing scope` names that start a pipeline node.
RUN_NODE_SITES = {
    "runner.py": ["MaaObserver.observe", "MirrorRunner.step"],
}

# file -> sorted scopes that call a page observer's own `.observe()`: the module door.
OBSERVER_CALLS = {
    "runner.py": ["observe"],
}

# The diagnostics that do their own bounded reads (they are not the product loop).
TOOL_SITES = ("battle_auto_assign.py", "battle_step.py", "map_advance.py")


def _calls(source, name):
    """Every call to `name` in `source`, with the dotted scope that encloses it."""
    found = set()

    def walk(node, owner):
        if isinstance(node, ast.ClassDef):
            owner = f"{owner}.{node.name}" if owner else node.name
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = f"{owner}.{node.name}" if owner else node.name
        if isinstance(node, ast.Call):
            func = node.func
            called = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None)
            if called == name:
                found.add(owner or "<module>")
        for child in ast.iter_child_nodes(node):
            walk(child, owner)

    walk(ast.parse(source), "")
    return sorted(found)


def _observer_calls(source):
    """Scopes that call `observer.observe(...)` on a page observer specifically.

    `transaction.observe(offers)` and friends share the method name but read no page,
    so the receiver is what separates the two protocols: a page observer is the local
    named `observer`, or `self.observer` on the runner.
    """
    found = set()

    def walk(node, owner):
        if isinstance(node, ast.ClassDef):
            owner = f"{owner}.{node.name}" if owner else node.name
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = f"{owner}.{node.name}" if owner else node.name
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "observe":
            receiver = node.func.value
            named = receiver.id if isinstance(receiver, ast.Name) else None
            if named == "observer" or (isinstance(receiver, ast.Attribute)
                                       and receiver.attr == "observer"):
                found.add(owner or "<module>")
        for child in ast.iter_child_nodes(node):
            walk(child, owner)

    walk(ast.parse(source), "")
    return sorted(found)


def _inventory(finder):
    inventory = {}
    for path in sorted(SOURCE.glob("*.py")):
        names = finder(path.read_text(encoding="utf-8"))
        if names:
            inventory[path.name] = names
    return inventory


def test_the_native_read_door_is_the_only_place_a_node_is_started():
    assert _inventory(lambda source: _calls(source, "run_node")) == RUN_NODE_SITES, (
        "a new site starts a pipeline node: route it through runner.bounded_read "
        "(or add it to RUN_NODE_SITES with the measurement that says it is bounded)")


def test_only_the_door_reads_a_page_observer():
    assert _inventory(_observer_calls) == OBSERVER_CALLS, (
        "a new site reads an observer directly: call runner.observe so the read is "
        "bounded and its record is completed")


def test_the_counter_example_a_new_read_would_be_caught():
    """The guard's own detectors: fresh calls of either shape are visible to it."""

    snippet = '''
class Reader:
    def page(self):
        return observer.observe(deadline=None)

def _new_page_reader(tasker):
    return run_node(tasker, 'MapObserve', None)
'''
    assert _calls(snippet, "run_node") == ["_new_page_reader"]
    assert _observer_calls(snippet) == ["Reader.page"]


def test_the_replay_observer_still_reads_frames(tmp_path):
    """The door may not break the offline half: a replayed frame is still a page."""

    from maalimbus.runner import FrameObserver, observe

    frame = {"scene": "MAP", "size": [1920, 1080], "ocr": []}
    reader = FrameObserver(tmp_path, frames=[frame])
    record = observe(reader)
    assert record["scene"] == "MAP"
    assert reader.index == 1
