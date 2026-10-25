"""一个判不了的 commit 不能永久挡住后面每一次运行（D293）。"""
import pathlib, json, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from maalimbus import floor_gift_transaction as tx


def _ledger(tmp_path, *, scope='old-run', kind='commit', pending=True):
    path = tmp_path / 'user-floor-gift-transaction.json'
    data = {'schema': 1, 'scope': scope, 'offer': 'sig', 'selected': ['A'], 'adopted': False,
            'pending': {'kind': kind, 'proof': 'f.png'} if pending else {}, 'completed': False}
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def _count():
    return {'chosen': 0, 'required': 1}


def test_a_pending_commit_from_another_run_refuses_until_it_is_retired(tmp_path):
    path = _ledger(tmp_path)
    book = tx.FloorGiftTransaction(path)
    try:
        book.prepare('new-run', [], _count(), 'frame.png')
    except ValueError as error:
        assert 'floor_gift_previous_transaction_unresolved' in str(error)
    else:  # pragma: no cover
        raise AssertionError('a pending commit from another run must refuse')
    retired = book.retire_stale_commit('new-run')
    assert retired and retired['kind'] == 'commit'
    assert book.data['pending'] == {}
    assert book.data['history'][-1]['abandoned']['kind'] == 'commit'


def test_the_retired_record_keeps_its_evidence(tmp_path):
    path = _ledger(tmp_path)
    book = tx.FloorGiftTransaction(path)
    book.retire_stale_commit('new-run')
    kept = book.data['history'][-1]
    assert kept['selected'] == ['A'] and kept['offer'] == 'sig'
    assert kept['abandoned']['scope'] == 'old-run'


def test_retiring_is_idempotent_and_never_touches_the_run_that_owes_it(tmp_path):
    path = _ledger(tmp_path)
    book = tx.FloorGiftTransaction(path)
    assert book.retire_stale_commit('new-run') is not None
    assert book.retire_stale_commit('new-run') is None
    same = _ledger(tmp_path, scope='new-run')
    assert tx.FloorGiftTransaction(same).retire_stale_commit('new-run') is None


def test_a_run_that_ended_unfinished_does_not_block_the_next_page(tmp_path):
    path = _ledger(tmp_path, pending=False)
    book = tx.FloorGiftTransaction(path)
    retired = book.retire_stale_run('new-run')
    assert retired and retired['scope'] == 'old-run'
    assert book.data['pending'] == {} and book.data['completed'] is False
    assert book.data['history'][-1]['abandoned']['scope'] == 'old-run'


def test_a_completed_record_is_not_retired_and_the_owner_is_never_touched(tmp_path):
    path = _ledger(tmp_path, pending=False)
    path.write_text(json.dumps({'schema': 1, 'scope': 'old-run', 'offer': 'sig',
                                'selected': ['A'], 'pending': {}, 'completed': True}),
                    encoding='utf-8')
    assert tx.FloorGiftTransaction(path).retire_stale_run('new-run') is None
    same = _ledger(tmp_path, scope='new-run', pending=False)
    assert tx.FloorGiftTransaction(same).retire_stale_run('new-run') is None
