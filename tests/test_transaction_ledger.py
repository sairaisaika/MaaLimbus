"""The transaction ledger: everything the loop writes down is read back again.

The risk this pins is duplicate spending: a reservation written before an input
whose reader never exists means an interrupted run cannot tell the next run what
it already bought.  ``shop_tx.reconcile_purchase`` and ``shop_tx.reconcile_refresh``
are the readers of a reserved purchase and they appear in ``MirrorRunner.step``
only as bare attribute references, so a call-site census sees nothing -- which is
why the ledger counts injections.
"""

from __future__ import annotations

import json

import pytest

from maalimbus import transaction_ledger as ledger


def test_every_intent_in_the_loop_has_a_reader():
    assert ledger.unpaired() == []


def test_the_two_shop_reconcilers_are_readers_even_though_no_call_site_names_them():
    source = ledger.RUNNER.read_text(encoding='utf-8')
    assert 'reconcile_purchase(' not in source
    assert 'reconcile_refresh(' not in source
    book = ledger.ledger()
    assert 'reconcile_purchase' in book['shop_tx']['injected']
    assert 'reconcile_refresh' in book['shop_tx']['injected']
    assert book['shop_tx']['intents']


def test_the_family_rules_place_the_real_api():
    for method in ('intent', 'reserve_purchase', 'reserve_refresh', 'refuse_owned',
                   'confirm_clear', 'receipt_intent', 'refusal_confirm_intent'):
        assert ledger.family(method) == 'intent', method
    for method in ('observe', 'observe_receipt', 'reconcile_purchase', 'commit',
                   'recover_pick'):
        assert ledger.family(method) == 'reconcile', method
    for method in ('prepare', 'close_visit', 'retire_pending', 'begin_visit'):
        assert ledger.family(method) == 'cleanup', method
    for method in ('matches', 'refreshes_used', 'signature', 'validate',
                   'notice_matches_a_pick', 'bought_names'):
        assert ledger.family(method) == 'query', method


def test_a_method_the_rules_cannot_place_is_named():
    assert ledger.family('spend_coins') == 'unknown'
    assert ledger.family('maybe_buy') == 'unknown'


def test_a_new_call_the_rules_cannot_place_shows_up_in_the_loop():
    source = '''
class MirrorRunner:
    def step(self):
        self.theme_transaction.spend_coins(self.run_id)
'''
    rows = ledger.sites(source)
    assert [(row['receiver'], row['method'], row['family']) for row in rows] == [
        ('self.theme_transaction', 'spend_coins', 'unknown')]


def test_an_intent_with_no_reader_is_reported():
    source = '''
class MirrorRunner:
    def step(self):
        self.theme_transaction.intent(self.run_id, 1, 'MAP', proof)
'''
    assert ledger.unpaired(source) == ['self.theme_transaction']


def test_an_injected_reader_counts_as_a_reader():
    source = '''
class MirrorRunner:
    def step(self):
        self.theme_transaction.intent(self.run_id, 1, 'MAP', proof)
        helper(reconcile=self.theme_transaction.observe)
'''
    assert ledger.unpaired(source) == []
    assert ledger.ledger(source)['self.theme_transaction']['injected'] == ['observe']


def test_a_field_is_not_a_method():
    source = '''
class MirrorRunner:
    def step(self):
        record = (self.theme_transaction.data or {}).get('pending')
'''
    rows = ledger.sites(source)
    families = {row['method']: row['family'] for row in rows}
    assert families.get('data') == 'query'


def test_the_ledger_sees_every_transaction_receiver_in_the_loop():
    book = ledger.ledger()
    for receiver in ('self.initial_transaction', 'self.floor_gift_transaction',
                     'self.theme_transaction', 'self.deployment_transaction',
                     'self.grace_transaction', 'shop_tx'):
        assert receiver in book, receiver


def test_no_transaction_method_is_left_unclassified():
    unclassified = sorted({method for methods in ledger.api().values()
                           for method, family in methods.items() if family == 'unknown'})
    assert unclassified == []


def test_the_public_dead_api_only_shrinks():
    assert ledger.dead_api() == ['deployment_transaction.revived_cards',
                                 'grace_transaction.adopt_unspent_entry_settings']


def test_the_tool_reports_clean(capsys):
    assert ledger.main([]) == 0
    out = capsys.readouterr().out
    assert 'intents nothing reads back: none' in out
    assert 'methods the loop calls that the families cannot place: none' in out
    assert 'reconcile_purchase, reconcile_refresh' in out


def test_the_tool_can_fail_a_source_that_leaves_an_intent_unread(capsys):
    source = '''
class MirrorRunner:
    def step(self):
        self.theme_transaction.intent(self.run_id, 1, 'MAP', proof)
'''
    assert ledger.main(['--source', 'build/none.py']) == 1
    assert 'no such file' in capsys.readouterr().err
    assert ledger.unpaired(source) == ['self.theme_transaction']


def test_a_prefix_that_looks_like_two_families_keeps_one_answer():
    # ``reserve_confirm`` starts with ``reserve`` (intent) and contains ``confirm``;
    # the rule order decides, and it must stay decided the same way.
    assert ledger.family('reserve_confirm') == 'intent'
    assert ledger.family('confirm_clear') == 'intent'
    assert ledger.family('reconcile_purchase') == 'reconcile'
    assert ledger.family('close_visit') == 'cleanup'


def test_the_reconciliation_of_a_reservation_is_an_attribute_reference_in_the_runner():
    rows = [row for row in ledger.sites() if row['receiver'] == 'shop_tx']
    assert any(row['injected'] and row['method'].startswith('reconcile_') for row in rows)
    assert any(not row['injected'] and row['family'] == 'intent' for row in rows)
