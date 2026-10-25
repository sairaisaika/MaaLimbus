"""The deployment order is a reading of the page's 1-12 badges (D282)."""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.team_order import order_from_badges  # noqa: E402

# The eleven measured cards plus one gap, read from
# evidence/runtime/packaged-mirror-20261025-080758/frame-0008.json: the badges are
# printed on the twelve fixed cards, so their numbers are the deployment order.
LIVE = [3, 5, 9, 11, 12, 8, 7, 4, 1, 2, 6, 10]


def test_a_full_permutation_reads_as_the_deployment_order():
    order, reason = order_from_badges(LIVE)
    assert reason == 'badges'
    # position 1 is card index 8 (the ninth card), position 12 is card index 4
    assert order[0] == 9 and order[-1] == 5
    assert sorted(order) == list(range(1, 13))


def test_the_order_is_the_inverse_of_the_badges():
    order, _ = order_from_badges(LIVE)
    for slot, badge in enumerate(LIVE, 1):
        assert order[badge - 1] == slot


def test_a_missing_badge_is_named_not_guessed():
    values = list(LIVE); values[3] = None
    assert order_from_badges(values) == (None, 'badge_missing')


def test_a_duplicate_badge_is_named_not_guessed():
    values = list(LIVE); values[0] = values[1]
    assert order_from_badges(values) == (None, 'badge_duplicate')


def test_a_badge_outside_the_grid_is_named_not_guessed():
    values = list(LIVE); values[0] = 13
    assert order_from_badges(values) == (None, 'badge_range')


def test_a_short_reading_is_named_not_guessed():
    assert order_from_badges(LIVE[:11]) == (None, 'badge_count')
    assert order_from_badges(()) == (None, 'badge_count')


def test_the_loop_reads_the_order_before_it_deploys():
    tree = ast.parse((ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8'))
    imported = {alias.name for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module == 'team_order'
                for alias in node.names}
    assert imported == {'order_from_badges'}, imported
    called = [node for node in ast.walk(tree)
              if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'order_from_badges']
    assert called, 'the loop must ask the page for the order'
