import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent


def _tool():
    spec = importlib.util.spec_from_file_location("audit_node_labels", REPO / "tools" / "audit_node_labels.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _click(kind, outcome="accepted"):
    return {"event": "map_click_result", "kind": kind, "outcome": outcome}


def test_the_page_after_a_click_is_the_label():
    tool = _tool()
    rows = [_click("gold_badge_node"), {"event": "loop_heartbeat", "page": "BATTLE_HUD"}]
    assert tool.landed_page(rows, 0) == "BATTLE_HUD"


def test_a_run_that_stopped_first_has_no_label():
    tool = _tool()
    rows = [_click("lit_icon"), {"event": "mirror_loop_stopped", "reason": "x"}]
    assert tool.landed_page(rows, 0) is None


def test_a_row_without_a_page_is_skipped():
    tool = _tool()
    rows = [_click("lit_icon"), {"event": "window_intent"}, {"event": "map_observed", "scene": "MAP"}]
    assert tool.landed_page(rows, 0) == "MAP"


def test_pairing_keeps_the_kind_and_the_landing():
    tool = _tool()
    rows = [_click("lit_icon"), {"event": "map_observed", "scene": "NODE_PANEL"}]
    found = tool.pairs(rows)
    assert found == [{"kind": "lit_icon", "outcome": "accepted", "landed": "NODE_PANEL", "point": None}]


def test_a_missing_kind_is_reported_as_unrecorded_not_dropped():
    tool = _tool()
    rows = [{"event": "map_click_result", "outcome": "rejected"},
            {"event": "map_observed", "scene": "MAP"}]
    table = tool.table(tool.pairs(rows))
    assert table[("unrecorded", "MAP")] == 1


def test_a_kind_that_splits_across_pages_is_visible_in_the_table():
    tool = _tool()
    rows = [_click("gold_badge_node"), {"event": "map_observed", "scene": "MAP"},
            _click("gold_badge_node"), {"event": "map_observed", "scene": "NODE_PANEL"}]
    table = tool.table(tool.pairs(rows))
    assert table[("gold_badge_node", "MAP")] == 1
    assert table[("gold_badge_node", "NODE_PANEL")] == 1
