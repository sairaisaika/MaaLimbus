"""The purchase label is the run's own later return, and it is re-derived, never trusted."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import shop_value_training as training  # noqa: E402


def _entry(kind, digest, **extra):
    return dict(kind=kind, **extra,
                evidence=dict(kind=kind, evidence='/runs/pi-x/frame-0001.json', sha256=digest),
                image_sha256=digest)


def test_the_label_is_the_runs_own_later_observation():
    """A floor clear is worth its floor, a victory the whole thing, nothing still something."""
    entries = [_entry('floor_clear', 'a' * 64, floor=2), _entry('floor_clear', 'b' * 64, floor=4)]
    derived = training.label_from_outcomes(entries)
    assert derived['benefit'] == pytest.approx(0.8)
    assert derived['observations'] == 2
    # The digest is over the bound bits, so the order the evidence arrived in cannot matter.
    assert derived['outcomes_digest'] == training.label_from_outcomes(list(reversed(entries)))['outcomes_digest']
    assert training.label_from_outcomes([_entry('final_victory', 'c' * 64)])['benefit'] == 1.0
    assert training.label_from_outcomes([_entry('entry_returned', 'd' * 64)])['benefit'] == 0.1


def test_a_later_observation_without_a_bound_digest_is_not_a_label():
    assert training.label_from_outcomes([dict(kind='floor_clear', floor=2, evidence={})]) is None
    assert training.label_from_outcomes([dict(kind='floor_clear', floor=2)]) is None
    assert training.label_from_outcomes([]) is None
    assert training.label_from_outcomes(None) is None


def test_review_sample_approves_only_what_the_run_actually_observed(tmp_path):
    folder = tmp_path / 'sample'
    folder.mkdir()
    (folder / 'sample.json').write_text(json.dumps(
        dict(version=1, kind='purchase_outcome', name='Awe', scope='scope-a')), encoding='utf-8')
    (folder / 'outcome.json').write_text(json.dumps(
        dict(version=1, outcomes=[_entry('floor_clear', 'a' * 64, floor=3)],
             objective='observed_run_return_not_causal_gift_strength',
             human_approved=False, training_eligible=False)), encoding='utf-8')
    derived, problem = training.review_sample(folder)
    assert problem is None and derived['benefit'] == pytest.approx(0.6)
    review = json.loads((folder / 'review.json').read_text(encoding='utf-8'))
    outcome = json.loads((folder / 'outcome.json').read_text(encoding='utf-8'))
    assert review['status'] == 'approved' and review['benefit'] == derived['benefit']
    assert review['label_source'] == training.OBJECTIVE_LABEL_SOURCE
    assert review['outcomes_digest'] == derived['outcomes_digest']
    assert outcome['approved_by'] == training.OBJECTIVE_APPROVAL
    assert outcome['training_eligible'] is True and outcome['human_approved'] is False
    assert outcome['label']['outcomes_digest'] == derived['outcomes_digest']
    # Reviewing twice cannot drift the label or add a second opinion.
    again, problem = training.review_sample(folder)
    assert problem is None and again['outcomes_digest'] == derived['outcomes_digest']


def test_a_purchase_the_run_never_followed_up_stays_pending(tmp_path):
    folder = tmp_path / 'sample'
    folder.mkdir()
    (folder / 'sample.json').write_text(json.dumps(
        dict(version=1, kind='purchase_outcome', name='Awe', scope='scope-a')), encoding='utf-8')
    (folder / 'outcome.json').write_text(json.dumps(
        dict(version=1, outcomes=[], human_approved=False, training_eligible=False)), encoding='utf-8')
    assert training.review_sample(folder) == (None, 'delayed_outcome_evidence_missing')
    assert not (folder / 'review.json').exists()


def _episode(scope, sample, target):
    evidence = dict(content_address=sample,
                    hashes=dict(before=dict(json_sha256=sample, png_sha256=sample),
                                after=dict(json_sha256=sample, png_sha256=sample)),
                    outcome_sha256=[sample])
    return dict(scope=scope, rows=[dict(scope=scope, sample=sample, values=[0.0], target=target,
                                        evidence=evidence)])


class _Offer:
    def __init__(self, name, price):
        self.name, self.price, self.click, self.index = name, price, [10, 10], 0


def _artefact(tmp_path, *, participation):
    catalog = training.load_catalog(ROOT / 'assets/resource/base/gift-catalog.json')
    vocabulary = training.gift_vocabulary(catalog)
    keywords = training.keyword_vocabulary(catalog)
    episodes = [_episode('scope-a', 'a' * 64, 0.9), _episode('scope-b', 'b' * 64, 0.2)]
    card = dict(training_ready=True, synthetic=False, reviewed_episodes=2, reviewed_rows=2,
                production_enabled=False, participation=participation,
                verification=training.verification_summary(episodes))
    parameters = training.init_parameters(len(training.feature_names(vocabulary, keywords)), 4, 7)
    training.export_candidate(parameters, card, tmp_path / 'model', vocabulary=vocabulary,
                              keyword_vocabulary=keywords, min_episodes=1)
    return tmp_path / 'model', vocabulary


def test_a_promoted_candidate_reorders_the_offers_and_a_shadow_one_does_not(tmp_path):
    from maalimbus.shop_value_shadow import rank_preview
    root, vocabulary = _artefact(tmp_path, participation=training.PARTICIPATION_RANKED)
    names = list(vocabulary)[:3]
    offers = [_Offer(name, 100) for name in names]
    ordered, trace = rank_preview(offers, dict(coins=1000, reserve_coins=0), root)
    assert trace['neural_value_shadow_applied'] is True
    assert trace['neural_value_ranked'] is True and trace['participation'] == 'ranked'
    assert trace['reviewed_episodes'] == 2
    scores = [row['predicted_review_value'] for row in trace['scores']]
    expected = [offers[index] for index in sorted(range(len(offers)), key=lambda i: (-scores[i], i))]
    assert [offer.name for offer in ordered] == [offer.name for offer in expected]

    shadow_root, _ = _artefact(tmp_path / 'shadow', participation=training.PARTICIPATION_SHADOW)
    kept, shadow_trace = rank_preview(offers, dict(coins=1000, reserve_coins=0), shadow_root)
    assert shadow_trace['neural_value_ranked'] is False
    assert [offer.name for offer in kept] == names


def test_a_candidate_with_a_dataset_digest_that_does_not_re_derive_is_ignored(tmp_path):
    from maalimbus.shop_value_shadow import rank_preview
    root, vocabulary = _artefact(tmp_path, participation=training.PARTICIPATION_RANKED)
    body = json.loads((root / 'modelcard.json').read_text(encoding='utf-8'))
    body['dataset_sha256'] = 'f' * 64
    (root / 'modelcard.json').write_text(json.dumps(body), encoding='utf-8')
    offers = [_Offer(list(vocabulary)[0], 100)]
    ordered, trace = rank_preview(offers, dict(coins=1000, reserve_coins=0), root)
    assert trace['reason'] == 'invalid_value_candidate_rule_fallback'
    assert [offer.name for offer in ordered] == [offers[0].name]
