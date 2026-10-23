"""Every `map_observed` writer must declare the party field.

Negative case: `agent/recognition.py` has two writers for the same event name.  Only the
main observation wrote `map_player`, so a reader that keys on that field saw 0 readings on
a run whose frames all yielded a position offline (measured 2026-10-23, run
`packaged-mirror-20261023-160255`: `party_point` = (703,316) on five frames, journal 0).
A same-name event written by two sites with different fields is the defect; this ratchet
makes the divergence a failing test instead of a silent gap.
"""

import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "agent" / "recognition.py"


def _map_observed_calls(tree):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "record":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "map_observed":
            yield node


def test_every_map_observed_writer_declares_map_player():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = list(_map_observed_calls(tree))
    assert len(calls) >= 2, "the scan must see every writer, or it proves nothing"
    missing = []
    for call in calls:
        keywords = {kw.arg for kw in call.keywords}
        if "map_player" not in keywords:
            missing.append(call.lineno)
    assert not missing, f"map_observed written without map_player at line(s) {missing}"
