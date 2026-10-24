"""D148: a commitment that was retired is not a debt.

Measured on `packaged-mirror-20261024-170840`: the ledger held `commit_sent True` with
`pending None` (D143 retired it) and the receipt stage stopped the run on a screen that
had no notice to print and nothing to match.
"""
from maalimbus.floor_gift_transaction import receipt_owed


def _data(**fields):
    record = {"selected": [], "receipts": [], "pending": None, "commit_sent": False}
    record.update(fields)
    return record


def test_a_pending_commit_owes_a_receipt():
    assert receipt_owed(_data(pending={"kind": "commit", "title": "A"}, commit_sent=True)) is True


def test_a_retired_commit_owes_nothing():
    assert receipt_owed(_data(pending=None, commit_sent=True)) is False


def test_a_selection_without_its_receipt_still_owes_one():
    assert receipt_owed(_data(selected=["A"], commit_sent=True)) is True


def test_a_selection_that_was_booked_owes_nothing():
    assert receipt_owed(_data(selected=["A"], receipts=[{"title": "A"}], commit_sent=True)) is False


def test_a_pending_receipt_is_not_itself_a_debt():
    assert receipt_owed(_data(pending={"kind": "receipt"}, selected=[], receipts=[{"title": "A"}])) is False


def test_an_empty_ledger_owes_nothing():
    assert receipt_owed({}) is False


def test_a_receipt_waits_for_a_page_that_can_print_one():
    """D150: the debt is only observable where a notice can appear."""
    import inspect
    import maalimbus.runner as runner
    source = inspect.getsource(runner.MirrorRunner.step)
    assert 'page_vocabulary.prints_a_gift_receipt(page)' in source
    from maalimbus import pages
    assert pages.prints_a_gift_receipt('GIFT_GET') is True
    assert pages.prints_a_gift_receipt('BATTLE_HUD') is False
    assert 'floor_receipt_awaits_a_printing_page' in source
    # and the stop is still reachable from a printing page
    assert "'floor_gift_receipt_unknown_repeated_or_pending')" in source
