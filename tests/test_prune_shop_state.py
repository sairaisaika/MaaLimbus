"""The shop-state prune tool: names in, records out, writing only when it changed."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'src'))

import prune_shop_state as tool  # noqa: E402
from maalimbus.storage import read_json  # noqa: E402


def a_store():
    """A store shaped like the bloated one: a pending context holding whole records."""
    return dict(version=1, scope='scope', visits={}, current_visit='1',
                bought=[dict(name='Emerald Elytra', price=160,
                             decision_context=dict(owned_bought=[], wanted=['Prestige Card']))],
                pending=dict(name='Tangled Bundle', price=159,
                             decision_context=dict(
                                 owned_bought=[dict(name='Emerald Elytra', price=160)])))


def test_prune_store_reduces_every_owned_bought_to_names():
    store, changed = tool.prune_store(a_store())
    assert changed == 1
    assert store['pending']['decision_context']['owned_bought'] == ['Emerald Elytra']
    assert store['bought'][0]['decision_context']['wanted'] == ['Prestige Card']


def test_prune_store_is_idempotent_and_leaves_names_alone():
    once, _ = tool.prune_store(a_store())
    twice, changed = tool.prune_store(once)
    assert changed == 0
    assert twice == once


def test_prune_store_refuses_a_shape_it_does_not_know():
    store = a_store()
    store['pending']['decision_context']['owned_bought'] = [7]
    pruned, changed = tool.prune_store(store)
    assert changed == 0
    assert pruned == store


def test_main_writes_only_when_it_changed_and_honours_dry_run(tmp_path):
    path = tmp_path / 'user-shop-scope.json'
    path.write_text(json.dumps(a_store()), encoding='utf-8')
    assert tool.main(['--path', str(path), '--dry-run']) == 0
    assert read_json(path)['pending']['decision_context']['owned_bought'] != ['Emerald Elytra']
    assert tool.main(['--path', str(path)]) == 0
    assert read_json(path)['pending']['decision_context']['owned_bought'] == ['Emerald Elytra']
    settled = path.stat().st_size
    assert tool.main(['--path', str(path)]) == 0
    assert path.stat().st_size == settled
