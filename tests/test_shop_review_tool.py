"""The review gate must be operable, and must not manufacture eligibility.

`tools/review_shop_purchase.py` is the only writer of `review.json`, and the training
loader re-verifies the retained evidence after it, so these tests pin both halves: a
decision is recorded exactly as the loader reads it, and `--eligible` is refused unless
`verify_episode_evidence` re-reads the bytes and the run ledger and verifies them.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('review_shop_purchase', ROOT / 'tools/review_shop_purchase.py')
review_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(review_tool)


def _folder(tmp_path, *, status='pending', benefit=None, notes=''):
    folder = tmp_path / 'a-sample-folder'
    folder.mkdir(parents=True)
    (folder / 'sample.json').write_text(json.dumps(dict(
        kind='purchase_outcome', version=1, scope='scope-1', name='Blue Zippo Lighter',
        price=10, coins_before=20, coins_after=10)), encoding='utf-8')
    review = dict(status=status, notes=notes)
    if benefit is not None:
        review['benefit'] = benefit
    (folder / 'review.json').write_text(json.dumps(review), encoding='utf-8')
    (folder / 'outcome.json').write_text(json.dumps(dict(
        version=1, human_approved=False, training_eligible=False, outcomes=[],
        reason='context_and_independent_episode_quality_review_required')), encoding='utf-8')
    return folder


def test_describe_reads_what_the_folder_claims(tmp_path):
    item = review_tool.describe(_folder(tmp_path))
    assert (item['scope'], item['name'], item['price']) == ('scope-1', 'Blue Zippo Lighter', 10)
    assert (item['review_status'], item['benefit']) == ('pending', None)
    assert item['outcome_eligible'] is False


def test_a_decision_needs_exactly_one_verdict_and_a_note(tmp_path):
    folder = _folder(tmp_path)
    with pytest.raises(ValueError):
        review_tool.decide(folder, approve=True, reject=True, note='both')
    with pytest.raises(ValueError):
        review_tool.decide(folder, approve=True, benefit=0.5)
    with pytest.raises(ValueError):
        review_tool.decide(folder, benefit=0.5, note='no verdict')


def test_a_label_must_be_a_number_in_zero_to_one(tmp_path):
    folder = _folder(tmp_path)
    for bad in (True, 'high', 1.5, -0.1):
        with pytest.raises(ValueError):
            review_tool.decide(folder, approve=True, benefit=bad, note='x')


def test_approving_records_the_label_and_the_note(tmp_path):
    folder = _folder(tmp_path)
    decided = review_tool.decide(folder, approve=True, benefit=0.6, note='worth the coins', reviewed_by='tester')
    assert (decided['review_status'], decided['benefit'], decided['notes']) == ('approved', 0.6, 'worth the coins')
    stored = json.loads((folder / 'review.json').read_text(encoding='utf-8'))
    assert (stored['status'], stored['benefit'], stored['reviewed_by']) == ('approved', 0.6, 'tester')
    assert stored['reviewed_at']
    # The evidence is not touched by a label.
    assert json.loads((folder / 'outcome.json').read_text(encoding='utf-8'))['training_eligible'] is False


def test_rejecting_drops_any_label(tmp_path):
    folder = _folder(tmp_path)
    review_tool.decide(folder, approve=True, benefit=0.6, note='first pass')
    decided = review_tool.decide(folder, reject=True, note='second look said no')
    assert (decided['review_status'], decided['benefit']) == ('rejected', None)
    assert 'benefit' not in json.loads((folder / 'review.json').read_text(encoding='utf-8'))


def test_eligible_is_refused_when_the_evidence_does_not_verify(tmp_path):
    folder = _folder(tmp_path)
    before = (folder / 'outcome.json').read_text(encoding='utf-8')
    with pytest.raises(ValueError, match='does not verify'):
        review_tool.decide(folder, approve=True, benefit=0.4, eligible=True, note='looks fine')
    assert (folder / 'outcome.json').read_text(encoding='utf-8') == before
    # The refusal happens before the label is written, so a rejected eligibility leaves no
    # half-recorded decision behind.
    assert json.loads((folder / 'review.json').read_text(encoding='utf-8'))['status'] == 'pending'


def test_find_folder_matches_a_name_prefix_or_a_scope(tmp_path):
    folder = _folder(tmp_path)
    assert review_tool.find_folder(tmp_path, 'a-sample') == folder
    assert review_tool.find_folder(tmp_path, 'scope-1') == folder
    assert review_tool.find_folder(tmp_path, 'nothing-like-this') is None
