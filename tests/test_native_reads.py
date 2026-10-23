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
    "runner.py": ["MaaObserver.observe", "MirrorRunner._act"],
}

# The doors a `run_node` call may hand its deadline to: a bare deadline is the defect.
BOUNDED_DOORS = ("bounded_read", "bounded_action")

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


def _door_name(node):
    """The door a call names, when it names one of them."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    called = func.id if isinstance(func, ast.Name) else (
        func.attr if isinstance(func, ast.Attribute) else None)
    return called if called in BOUNDED_DOORS else None


def _walk_scopes(node, owner, visit):
    """Depth-first walk that keeps the dotted scope of the node it is visiting."""
    if isinstance(node, ast.ClassDef):
        owner = f"{owner}.{node.name}" if owner else node.name
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        owner = f"{owner}.{node.name}" if owner else node.name
    visit(node, owner)
    for child in ast.iter_child_nodes(node):
        _walk_scopes(child, owner, visit)


def _unbounded_nodes(source):
    """Every `run_node(...)` whose window did not come from one of the two doors.

    The inventory above says *where* a node is started; this says *what window* it is
    given.  They are different defects: `dea7028` bounded one site and left the other
    naming `self.deadline`, a whole run's budget for one read.  So the third argument
    has to be a door call -- or a local the *same scope* assigned from one, which is
    what a site needs when it also has to record the window before spending it.
    """
    tree = ast.parse(source)
    doors = {}

    def collect(node, owner):
        if isinstance(node, ast.Assign) and _door_name(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    doors.setdefault(owner, set()).add(target.id)

    _walk_scopes(tree, "", collect)

    offences = []

    def check(node, owner):
        if isinstance(node, ast.Call):
            func = node.func
            called = func.id if isinstance(func, ast.Name) else None
            if called == "run_node":
                window = node.args[2] if len(node.args) >= 3 else None
                allowed = bool(_door_name(window)) or (
                    isinstance(window, ast.Name) and window.id in doors.get(owner, ()))
                if not allowed:
                    offences.append(f"{owner}:{getattr(node, 'lineno', '?')}")

    _walk_scopes(tree, "", check)
    return offences


def test_every_node_start_hands_over_its_own_bound():
    offenders = _inventory(_unbounded_nodes)
    assert offenders == {}, (
        "a run_node call was handed something other than bounded_read/bounded_action: "
        "one native call may not get the whole run's budget")


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
    assert _unbounded_nodes(snippet), "a bare deadline at a new site must be visible"


def test_every_node_start_names_its_bound_in_the_source():
    """The counter-example for the door rule: a bare deadline is reported."""
    unbounded = """
def _old_style(self):
    return run_node(self.tasker, plan['node'], self.deadline)
"""
    bounded = """
def _new_style(self):
    return run_node(self.tasker, plan['node'], bounded_action(self.deadline))
"""
    assert _unbounded_nodes(unbounded) == ["_old_style:3"]
    assert _unbounded_nodes(bounded) == []


def test_the_replay_observer_still_reads_frames(tmp_path):
    """The door may not break the offline half: a replayed frame is still a page."""

    from maalimbus.runner import FrameObserver, observe

    frame = {"scene": "MAP", "size": [1920, 1080], "ocr": []}
    reader = FrameObserver(tmp_path, frames=[frame])
    record = observe(reader)
    assert record["scene"] == "MAP"
    assert reader.index == 1
