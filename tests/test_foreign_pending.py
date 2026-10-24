"""A run inherits the reservation another run left open (D98).

Measured on `evidence/runtime/packaged-mirror-20261024-061628`: the deployment card
`...-055841` had reserved was still in the ledger, so the next run read
`Deployment_transaction.pending` for its whole window, sent **no click at all**, and
ended on `the_submitted_turn_never_showed_a_page`.  A card another scope reserved can
never be observed by this run, so it is retired with a record instead of being waited on.
"""

import json
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.deployment_transaction import DeploymentTransaction  # noqa: E402
from maalimbus import runner  # noqa: E402


def _ledger(tmp_path, scope, pending=None):
    path = tmp_path / 'user-deployment-transaction.json'
    data = {'scope': scope, 'order': [1], 'saved_order': None, 'unavailable': [],
            'sequence': [], 'pending': pending, 'submitted': False}
    path.write_text(json.dumps(data), encoding='utf-8')
    return DeploymentTransaction(path)


def _runner(tmp_path, transaction, run_id='run-new'):
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.run_id = run_id
    loop.notes = []
    loop.note = lambda name, **fields: loop.notes.append((name, fields))
    loop.deployment_transaction = transaction
    loop.theme_transaction = None
    loop.initial_transaction = None
    loop.floor_gift_transaction = None
    return loop


def test_a_card_another_run_reserved_is_retired_and_recorded(tmp_path):
    card = {'kind': 'card', 'before': 4, 'capacity': 12, 'card': 1}
    tx = _ledger(tmp_path, 'run-old', pending=card)
    loop = _runner(tmp_path, tx)
    loop._retire_foreign_pending()
    assert tx.data['pending'] is None
    abandoned = tx.data['abandoned']
    assert abandoned and abandoned[0]['scope'] == 'run-old'
    assert abandoned[0]['reason'] == 'a_previous_run_left_it_open'
    assert [name for name, _ in loop.notes] == ['stale_card_check', 'stale_card_retired']
    fields = loop.notes[1][1]
    assert fields['scope'] == 'run-old' and fields['kind'] == 'card'


def test_a_card_this_run_reserved_is_left_alone_by_the_ledger_api(tmp_path):
    """The ledgers own rule: a card of this scope is this run's business."""
    card = {'kind': 'card', 'before': 4, 'capacity': 12, 'card': 1}
    tx = _ledger(tmp_path, 'run-new', pending=card)
    assert tx.retire_foreign('run-new', 'not mine') is None
    assert tx.data['pending'] == card


def test_the_run_start_door_retires_whatever_the_previous_process_left(tmp_path):
    """A fresh run has reserved nothing, so a card in the file is not this run's."""
    card = {'kind': 'card', 'before': 4, 'capacity': 12, 'card': 1}
    tx = _ledger(tmp_path, 'run-new', pending=card)
    loop = _runner(tmp_path, tx)
    loop._retire_foreign_pending()
    assert tx.data['pending'] is None
    assert [name for name, _ in loop.notes] == ['stale_card_check', 'stale_card_retired']


def test_a_quiet_ledger_is_not_touched(tmp_path):
    tx = _ledger(tmp_path, 'run-old', pending=None)
    before = tx.path.read_text(encoding='utf-8')
    loop = _runner(tmp_path, tx)
    loop._retire_foreign_pending()
    assert tx.path.read_text(encoding='utf-8') == before
    assert loop.notes == []


def test_the_retirement_happens_before_the_first_step(tmp_path):
    source = (ROOT / 'src/maalimbus/runner.py').read_text(encoding='utf-8')
    walk = source[source.index('    def _walk(self'):]
    body = walk[:walk.index('while self.state')]
    assert '_retire_foreign_pending()' in body
    # and it is not a new page branch: the door is about the ledger, not the screen
    helper = source[source.index('    def _retire_foreign_pending(self)'):]
    helper = helper[:helper.index('    def _start_stall_watch(self)')]
    assert "page == " not in helper
