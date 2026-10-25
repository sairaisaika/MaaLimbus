"""A frame with no party must say so, not blame the nodes (D285)."""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.runner import party_anchor_gap  # noqa: E402


def test_a_read_party_has_no_gap():
    assert party_anchor_gap((1012, 595), [(1, 2, 3, 4)]) is None


def test_a_missing_party_with_no_candidates_names_the_candidate_gap():
    assert party_anchor_gap(None, []) == 'no_candidate'


def test_a_missing_party_that_still_offers_nodes_names_the_party_gap():
    assert party_anchor_gap(None, [(1, 2, 3, 4)]) == 'no_party'


def test_the_loop_writes_the_gap_as_its_own_event():
    source = (ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    records = [node for node in ast.walk(tree)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr == 'record' and node.args
               and isinstance(node.args[0], ast.Constant)
               and node.args[0].value == 'map_party_unread']
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'party_anchor_gap']
    assert calls, 'the loop must ask why the frame offers nothing'
    assert not records, 'the event is written through note(), not record()'
    assert "note('map_party_unread'" in source
