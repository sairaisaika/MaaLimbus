"""Isolated synthetic tests for the offline shop-value scaffold.

Assembling rows, fitting the tiny MLP, and exporting JSON are exercised here with
synthetic data only.  Passing these tests says the algorithm and the file formats
work; it says nothing about the game, and it lights up nothing at runtime.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from maalimbus import shop_value_training as training

ROOT = Path(__file__).resolve().parents[1]
REAL_CATALOG = ROOT / 'assets/resource/base/gift-catalog.json'


def tiny_catalog(path, names=('Alpha Gift', 'Beta Gift', 'Gamma Gift')):
    path.write_text(json.dumps(dict(version=1, gifts=[
        dict(name=name, keywords=['Poise'] if name != 'Beta Gift' else ['Bleed'], icons=[])
        for name in names])), encoding='utf-8')
    return path


def _write_frame(path, *, coins, offers, utc, scene='SHOP'):
    """A readable shop frame: one currency token, then each offer's price over its name.

    The geometry follows the readers: the currency badge sits in the coin ROI, and each
    name sits one ``NAME_ROW_OFFSET`` below its price badge, so ``_shelf``/``_coins``
    re-derive from these bytes exactly what the fixture claims they show.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    png = path.with_suffix('.png')
    png.write_bytes(b'\x89PNG\r\n\x1a\n' + path.name.encode('utf-8'))
    record = dict(size=[1920, 1080], scene=scene, utc=utc,
                  image_sha256=hashlib.sha256(png.read_bytes()).hexdigest(),
                  ocr=[dict(text=str(coins), score=0.99, box=[880, 180, 80, 40])])
    for index, (name, price) in enumerate(offers):
        y = 350 + index * 110
        record['ocr'].append(dict(text=str(price), score=0.99, box=[900, y, 80, 40]))
        record['ocr'].append(dict(text=name, score=0.99, box=[860, y + 14, 200, 40]))
    path.write_text(json.dumps(record, sort_keys=True), encoding='utf-8')
    return dict(path=str(path.resolve()), json_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                png_sha256=record['image_sha256'])


def _proof_from(path):
    """The proof record for evidence bytes that already exist."""
    path = Path(path)
    return dict(path=str(path.resolve()), json_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                png_sha256=hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest())


def sample_folder(root, key, *, scope='scope-1', name='Alpha Gift', price=120, coins=1000,
                  status='approved', benefit=0.8, eligible=True, action_executed=True,
                  context=None, utc='2026-10-12T12:00:00+00:00', others=(('Beta Gift', 200),),
                  approved_outcome=True, address=None, reuse=None):
    """One reviewable episode whose evidence bytes really hash as the sample says.

    The frames are synthetic, but nothing about them is asserted: the fixture writes
    real JSON and real PNG bytes, computes their real digests, names the folder by the
    real content address, and binds the delayed outcome through a run ledger exactly as
    the producers do -- so ``verify_episode_evidence`` accepts it on its own terms.
    """
    root = Path(root)
    runtime = root.parent / 'runtime'
    stamp = hashlib.sha256(('%s|%s|%s' % (key, scope, name)).encode()).hexdigest()[:12]
    if reuse is not None:
        # The same bytes standing in for a second, "independent" episode.
        before, after = _proof_from(Path(reuse) / 'before.json'), _proof_from(Path(reuse) / 'after.json')
        question = _proof_from(Path(reuse) / 'question.json')
        consequence = _proof_from(sorted(Path(reuse).glob('outcome-*.json'))[0])
        # Keep the ledger entry the reused folder already recorded, so the bytes stay
        # bound to the same scope and only the duplicate itself is the finding.
        event = dict(json.loads((Path(reuse) / 'outcome.json').read_text(encoding='utf-8'))['outcomes'][0]['evidence'])
    else:
        before = _write_frame(runtime / ('%s-before.json' % stamp), coins=coins,
                              offers=[(name, price), *others], utc=utc)
        after = _write_frame(runtime / ('%s-after.json' % stamp), coins=coins - price,
                             offers=list(others), utc=utc)
        question = _write_frame(runtime / ('%s-question.json' % stamp), coins=coins,
                                offers=[(name, price), *others], utc=utc)
        consequence = _write_frame(runtime / ('%s-consequence.json' % stamp), coins=coins - price,
                                   offers=list(others), utc='2026-10-12T13:00:00+00:00', scene='MAP')
        event = dict(kind='floor_clear', floor=4, evidence=consequence['path'],
                     sha256=consequence['json_sha256'])
    ledger_path = ledger_for(root)
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {}
    run = dict(id=scope, events={'floor_clear': event})
    ledger.update(version=1, active=None,
                  receipts=[r for r in ledger.get('receipts', []) if r.get('id') != scope] + [run],
                  completed_runs=int(ledger.get('completed_runs') or 0))
    ledger_path.write_text(json.dumps(ledger), encoding='utf-8')

    payload = dict(version=1, kind='purchase_outcome', scope=scope, visit='2', name=name, price=price,
                   coins_before=coins, coins_after=coins - price,
                   context=context if context is not None else
                   dict(keywords=['Poise'], wanted=['Alpha Gift', 'Beta Gift'], reserve_coins=0),
                   before=before, after=after, question=question,
                   receipt_teacher='native_exact_coin_delta_complete_shelf_and_item_status',
                   action_executed=action_executed, gift_causal_strength=None)
    folder = root / (address or hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'sample.json').write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')
    for role, proof in (('before', before), ('after', after), ('question', question)):
        for suffix, field in (('.json', 'json_sha256'), ('.png', 'png_sha256')):
            shutil.copyfile(Path(proof['path']).with_suffix(suffix), folder / (role + suffix))
    (folder / 'review.json').write_text(json.dumps(dict(status=status, benefit=benefit, notes='',
                                                        corrected_category=None)), encoding='utf-8')
    (folder / 'outcome.json').write_text(json.dumps(dict(
        version=1, category='purchase_completed_with_later_run_observations',
        outcomes=[dict(kind='floor_clear', floor=4, evidence=event,
                       image_sha256=consequence['png_sha256'])],
        objective='observed_run_return_not_causal_gift_strength', human_approved=approved_outcome,
        training_eligible=eligible, reason='isolated fixture')), encoding='utf-8')
    for suffix in ('.json', '.png'):
        shutil.copyfile(Path(consequence['path']).with_suffix(suffix),
                        folder / ('outcome-' + event['sha256'] + suffix))
    (folder / 'trace.log').write_text('Isolated fixture; not a game observation.\n', encoding='utf-8')
    return folder


def ledger_for(root):
    """The run ledger the fixtures bind their delayed outcomes through."""
    return Path(root).parent / 'user-run-ledger.json'


def reviewed_episodes(root, count, *, catalogue, rows_per_episode=1, **extra):
    for index in range(count):
        for row_index in range(rows_per_episode):
            sample_folder(root, 'episode-%02d-row-%d' % (index, row_index), scope='scope-%02d' % index,
                          name='Alpha Gift', price=120, benefit=0.9 - 0.1 * (index % 3), **extra)
    catalog = training.load_catalog(catalogue)
    return training.load_reviewed_episodes(root, catalog, ledger=ledger_for(root))


# ------------------------------------------------------------------ catalogue and encoding

def test_vocabulary_is_the_complete_sorted_catalogue():
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary = training.gift_vocabulary(catalog)
    assert len(vocabulary) == len(set(vocabulary))
    assert list(vocabulary) == sorted(vocabulary)
    assert 'Prestige Card' in vocabulary and "Devil's Share" in vocabulary


def test_feature_names_match_the_encoded_width():
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary, keywords = training.gift_vocabulary(catalog), training.keyword_vocabulary(catalog)
    encoded = training.encode_observation(dict(action='buy', offer_name='Prestige Card'),
                                          vocabulary=vocabulary, keyword_vocabulary=keywords)
    names = training.feature_names(vocabulary, keywords)
    assert encoded['width'] == len(names) == len(encoded['values'])
    assert names[list(vocabulary).index('Prestige Card')] == 'gift=Prestige Card'
    assert encoded['mask'] == list(encoded['mask'])


def test_a_known_gift_sets_its_own_position_and_the_known_flag():
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary, keywords = training.gift_vocabulary(catalog), training.keyword_vocabulary(catalog)
    encoded = training.encode_observation(dict(action='buy', offer_name='Prestige Card'),
                                          vocabulary=vocabulary, keyword_vocabulary=keywords)
    assert encoded['values'][list(vocabulary).index('Prestige Card')] == 1.0
    assert sum(encoded['values'][:len(vocabulary)]) == 1.0
    assert encoded['known_gift'] is True


def test_an_unknown_gift_never_lands_on_a_similar_name():
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary, keywords = training.gift_vocabulary(catalog), training.keyword_vocabulary(catalog)
    encoded = training.encode_observation(dict(action='buy', offer_name='Prestige Cards'),
                                          vocabulary=vocabulary, keyword_vocabulary=keywords)
    assert sum(encoded['values'][:len(vocabulary)]) == 0.0
    assert encoded['known_gift'] is False
    assert encoded['mask'][training.MASK_FIELDS.index('offer_name')] == 1.0


def test_missing_fields_are_masked_not_invented():
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary, keywords = training.gift_vocabulary(catalog), training.keyword_vocabulary(catalog)
    encoded = training.encode_observation(dict(action='skip'), vocabulary=vocabulary,
                                          keyword_vocabulary=keywords)
    for field in training.NUMERIC_FIELDS:
        assert encoded['mask'][training.MASK_FIELDS.index(field)] == 0.0
    for field in ('offer_name', 'keywords', 'owned', 'wanted'):
        assert encoded['mask'][training.MASK_FIELDS.index(field)] == 0.0
    assert encoded['values'][len(vocabulary):len(vocabulary) + len(training.ACTIONS)] == [0.0, 0.0, 1.0]


def test_keywords_set_their_own_position_and_unknown_keywords_contribute_nothing():
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary, keywords = training.gift_vocabulary(catalog), training.keyword_vocabulary(catalog)
    base = len(vocabulary) + len(training.ACTIONS)
    encoded = training.encode_observation(dict(action='buy', offer_name='Prestige Card',
                                               keywords=['Poise', 'Not A Keyword']),
                                          vocabulary=vocabulary, keyword_vocabulary=keywords)
    assert encoded['values'][base + list(keywords).index('Poise')] == 1.0
    assert sum(encoded['values'][base:base + len(keywords)]) == 1.0


def test_feasibility_flags_describe_affordability_and_the_reserve():
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary, keywords = training.gift_vocabulary(catalog), training.keyword_vocabulary(catalog)
    flags = training.FLAG_FIELDS
    base = len(training.feature_names(vocabulary, keywords)) - len(flags)
    rich = training.encode_observation(dict(action='buy', offer_name='Prestige Card', price=120,
                                            coins=1000, reserve_coins=0, refreshes_used=0,
                                            refresh_limit=2),
                                       vocabulary=vocabulary, keyword_vocabulary=keywords)
    broke = training.encode_observation(dict(action='buy', offer_name='Prestige Card', price=120,
                                             coins=100, reserve_coins=50),
                                        vocabulary=vocabulary, keyword_vocabulary=keywords)
    assert rich['values'][base + flags.index('affordable')] == 1.0
    assert rich['values'][base + flags.index('refresh_room')] == 1.0
    assert broke['values'][base + flags.index('affordable')] == 0.0
    assert broke['values'][base + flags.index('reserve_respected')] == 0.0


def test_encoding_is_pure_and_repeatable():
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary, keywords = training.gift_vocabulary(catalog), training.keyword_vocabulary(catalog)
    observation = dict(action='buy', offer_name='Prestige Card', price=250, coins=900,
                       keywords=['Poise'], owned=['Alpha'])
    before = json.dumps(observation, sort_keys=True)
    first = training.encode_observation(observation, vocabulary=vocabulary, keyword_vocabulary=keywords)
    second = training.encode_observation(observation, vocabulary=vocabulary, keyword_vocabulary=keywords)
    assert first['values'] == second['values']
    assert json.dumps(observation, sort_keys=True) == before


@pytest.mark.parametrize('bad', [
    dict(action='steal'), dict(action='buy', price=-1), dict(action='buy', coins='many'),
    dict(action='buy', offer_name=''), dict(action='buy', keywords='Poise'),
])
def test_bad_observations_are_refused(bad):
    with pytest.raises(ValueError):
        training.normalise_observation(bad)


# ------------------------------------------------------------------ model

def test_the_tiny_mlp_learns_a_synthetic_signal():
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary, keywords = training.gift_vocabulary(catalog), training.keyword_vocabulary(catalog)
    rows = []
    for index, (price, target) in enumerate([(60, 0.95), (90, 0.9), (250, 0.2), (300, 0.05)] * 4):
        observation = dict(action='buy', offer_name='Prestige Card', price=price, coins=1000,
                           reserve_coins=0, floor=2, refreshes_used=0, refresh_limit=2)
        encoded = training.encode_observation(observation, vocabulary=vocabulary, keyword_vocabulary=keywords)
        rows.append(dict(sample='synthetic-%d' % index, scope='scope-%d' % index,
                         values=encoded['values'], target=target))
    fitted = training.fit(rows, hidden=8, epochs=600, seed=3)
    assert fitted['metrics']['loss_end'] < fitted['metrics']['loss_start'] / 2
    assert fitted['metrics']['pairwise_accuracy'] >= 0.9
    assert len(fitted['history']) == 600


def test_training_is_deterministic_for_a_seed():
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary, keywords = training.gift_vocabulary(catalog), training.keyword_vocabulary(catalog)
    rows = []
    for index, price in enumerate([60, 120, 240, 300]):
        encoded = training.encode_observation(dict(action='buy', offer_name='Prestige Card', price=price,
                                                   coins=1000), vocabulary=vocabulary,
                                              keyword_vocabulary=keywords)
        rows.append(dict(sample='s-%d' % index, scope='scope-%d' % index, values=encoded['values'],
                         target=1.0 - price / 400.0))
    first = training.fit(rows, epochs=50, seed=11)
    second = training.fit(rows, epochs=50, seed=11)
    third = training.fit(rows, epochs=50, seed=12)
    assert first['parameters'] == second['parameters']
    assert first['parameters'] != third['parameters']


def test_pairwise_accuracy_ignores_ties():
    assert training.pairwise_accuracy([0.9, 0.1], [1.0, 0.0]) == dict(pairs=1, pairwise_accuracy=1.0)
    assert training.pairwise_accuracy([0.1, 0.9], [1.0, 1.0]) == dict(pairs=0, pairwise_accuracy=None)


def test_the_module_carries_no_pickle_and_writes_only_json():
    source = (ROOT / 'src/maalimbus/shop_value_training.py').read_text(encoding='utf-8')
    assert 'import pickle' not in source
    assert 'pickle.dump' not in source and 'pickle.load' not in source
    assert training.PRODUCTION_ENABLED is False


# ------------------------------------------------------------------ scope splitting

def test_scopes_never_straddle_the_split():
    episodes = [dict(scope='scope-%02d' % index, rows=[dict(sample='r', values=[0.0], target=0.5)])
                for index in range(10)]
    train, test = training.split_by_scope(episodes, test_fraction=0.3, seed=5)
    assert sorted([episode['scope'] for episode in train + test]) == sorted(
        [episode['scope'] for episode in episodes])
    assert not ({episode['scope'] for episode in train} & {episode['scope'] for episode in test})
    assert len(test) == 3
    again_train, again_test = training.split_by_scope(episodes, test_fraction=0.3, seed=5)
    assert [episode['scope'] for episode in again_train] == [episode['scope'] for episode in train]


def test_a_single_episode_has_no_held_out_side():
    train, test = training.split_by_scope([dict(scope='only', rows=[])], test_fraction=0.3, seed=1)
    assert [episode['scope'] for episode in train] == ['only'] and test == []


# ------------------------------------------------------------------ dataset eligibility

def test_the_real_sample_root_is_not_training_ready(tmp_path):
    real = ROOT / training.DEFAULT_SAMPLES
    if not real.is_dir():
        pytest.skip('no retained shop samples in this workspace')
    catalog = training.load_catalog(REAL_CATALOG)
    report = training.readiness_report(real, catalog)
    assert report['training_ready'] is False
    assert report['production_enabled'] is False
    assert report['reviewed_episodes'] == 0
    assert any(item['reason'] in ('review_not_approved', 'benefit_label_absent')
               for item in training.load_reviewed_episodes(real, catalog)['excluded'])


def test_a_pending_review_is_refused_and_becomes_no_row(tmp_path):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    samples = tmp_path / 'samples'
    folder = sample_folder(samples, 'pending', status='pending')
    dataset = training.load_reviewed_episodes(samples, training.load_catalog(catalog_path))
    assert dataset['ready'] is False and dataset['row_count'] == 0
    assert [item['reason'] for item in dataset['excluded']] == ['review_not_approved']
    assert dataset['excluded'][0]['sample'] == folder.name  # the content address, not the fixture label
    report = training.readiness_report(samples, training.load_catalog(catalog_path))
    assert report['exclusion_reasons'] == {'review_not_approved': 1}
    assert report['blockers']


def test_an_unbought_offer_is_never_a_negative_sample(tmp_path):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    samples = tmp_path / 'samples'
    sample_folder(samples, 'not-bought', action_executed=False, benefit=0.0)
    dataset = training.load_reviewed_episodes(samples, training.load_catalog(catalog_path))
    assert dataset['row_count'] == 0
    assert dataset['excluded'][0]['reason'] == 'no_purchase_is_not_a_negative_sample'


def test_a_review_without_a_benefit_label_is_refused(tmp_path):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    samples = tmp_path / 'samples'
    sample_folder(samples, 'unlabelled', benefit=None)
    dataset = training.load_reviewed_episodes(samples, training.load_catalog(catalog_path))
    assert dataset['row_count'] == 0
    assert dataset['excluded'][0]['reason'] == 'benefit_label_absent'


def test_an_ineligible_outcome_is_refused(tmp_path):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    samples = tmp_path / 'samples'
    sample_folder(samples, 'ineligible', eligible=False)
    dataset = training.load_reviewed_episodes(samples, training.load_catalog(catalog_path))
    assert dataset['excluded'][0]['reason'] == 'outcome_not_training_eligible'


def test_ten_reviewed_scopes_make_the_data_ready(tmp_path):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    samples = tmp_path / 'samples'
    dataset = reviewed_episodes(samples, 10, catalogue=catalog_path)
    assert dataset['ready'] is True and dataset['episode_count'] == 10 and dataset['row_count'] == 10
    assert dataset['blockers'] == []
    report = training.readiness_report(samples, training.load_catalog(catalog_path),
                                       ledger=ledger_for(samples))
    assert report['training_ready'] is True and len(report['scopes']) == 10
    assert report['verified_rows'] == 10 and report['dataset_sha256']


def test_nine_reviewed_scopes_are_still_not_enough(tmp_path):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    samples = tmp_path / 'samples'
    dataset = reviewed_episodes(samples, 9, catalogue=catalog_path)
    assert dataset['ready'] is False and dataset['episode_count'] == 9
    assert dataset['blockers'] == ['reviewed_episodes 9 < required 10']


# ------------------------------------------------------------------ evidence verification

def _dataset(tmp_path, *folders, **kwargs):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    samples = tmp_path / 'samples'
    for name, builder in folders:
        builder(samples)
    return training.load_reviewed_episodes(samples, training.load_catalog(catalog_path),
                                           ledger=ledger_for(samples)), samples


def _only_reason(dataset):
    assert dataset['row_count'] == 0 and len(dataset['excluded']) == 1, dataset['excluded']
    return dataset['excluded'][0]['reason']


def test_a_malformed_sample_json_is_an_exclusion_not_a_crash(tmp_path):
    def build(samples):
        folder = sample_folder(samples, 'malformed')
        (folder / 'sample.json').write_text('{not json', encoding='utf-8')
    dataset, _ = _dataset(tmp_path, ('malformed', build))
    assert _only_reason(dataset).startswith('sample_malformed')
    assert dataset['ready'] is False and dataset['blockers']


def test_a_sample_that_is_not_a_json_object_is_an_exclusion(tmp_path):
    def build(samples):
        folder = sample_folder(samples, 'list')
        (folder / 'sample.json').write_text('[1, 2]', encoding='utf-8')
    dataset, _ = _dataset(tmp_path, ('list', build))
    assert _only_reason(dataset) == 'sample_not_an_object'


def test_a_changed_evidence_png_is_an_exclusion(tmp_path):
    def build(samples):
        folder = sample_folder(samples, 'swapped')
        (folder / 'after.png').write_bytes(b'\x89PNG\r\n\x1a\nnot the frame that was reviewed')
    dataset, _ = _dataset(tmp_path, ('swapped', build))
    reason = _only_reason(dataset)
    assert reason.startswith('evidence_after_') and 'hash' in reason


def test_a_changed_sample_json_no_longer_matches_its_content_address(tmp_path):
    def build(samples):
        folder = sample_folder(samples, 'edited')
        payload = json.loads((folder / 'sample.json').read_text(encoding='utf-8'))
        payload['visit'] = '3'
        (folder / 'sample.json').write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')
    dataset, _ = _dataset(tmp_path, ('edited', build))
    assert _only_reason(dataset) == 'sample_content_address_differs'


def test_a_delayed_outcome_the_scope_does_not_bind_is_an_exclusion(tmp_path):
    def build(samples):
        folder = sample_folder(samples, 'foreign')
        ledger_path = ledger_for(samples)
        ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
        run = ledger['receipts'][0]
        run['events']['floor_clear']['sha256'] = '0' * 64
        ledger_path.write_text(json.dumps(ledger), encoding='utf-8')
        return folder
    dataset, _ = _dataset(tmp_path, ('foreign', build))
    assert _only_reason(dataset) == 'delayed_outcome_not_bound_to_the_scope'


def test_a_delayed_outcome_from_another_scope_is_an_exclusion(tmp_path):
    def build(samples):
        sample_folder(samples, 'other', scope='scope-other')
        folder = sample_folder(samples, 'mine', scope='scope-1')
        ledger_path = ledger_for(samples)
        ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
        ledger['receipts'] = [run for run in ledger['receipts'] if run['id'] != 'scope-1']
        ledger_path.write_text(json.dumps(ledger), encoding='utf-8')
        return folder
    dataset, _ = _dataset(tmp_path, ('mine', build))
    reasons = {item['reason'] for item in dataset['excluded']}
    assert 'delayed_outcome_scope_not_in_run_ledger' in reasons


def test_a_missing_delayed_outcome_evidence_copy_is_an_exclusion(tmp_path):
    def build(samples):
        folder = sample_folder(samples, 'nocopy')
        for path in folder.glob('outcome-*.json'):
            path.unlink()
    dataset, _ = _dataset(tmp_path, ('nocopy', build))
    assert _only_reason(dataset) == 'delayed_outcome_copy_missing'


def test_an_outcome_without_any_delayed_evidence_is_an_exclusion(tmp_path):
    def build(samples):
        folder = sample_folder(samples, 'empty-outcome')
        label = json.loads((folder / 'outcome.json').read_text(encoding='utf-8'))
        label['outcomes'] = []
        (folder / 'outcome.json').write_text(json.dumps(label), encoding='utf-8')
    dataset, _ = _dataset(tmp_path, ('empty', build))
    assert _only_reason(dataset) == 'delayed_outcome_evidence_missing'


def test_an_unapproved_outcome_is_an_exclusion(tmp_path):
    def build(samples):
        sample_folder(samples, 'unapproved', approved_outcome=False)
    dataset, _ = _dataset(tmp_path, ('unapproved', build))
    assert _only_reason(dataset) == 'outcome_not_human_approved'


def test_one_purchase_cannot_stand_in_for_two_scopes(tmp_path):
    def build(samples):
        first = sample_folder(samples, 'first', scope='scope-a', name='Alpha Gift')
        sample_folder(samples, 'second', scope='scope-b', name='Alpha Gift', reuse=first)
    dataset, _ = _dataset(tmp_path, ('reused', build))
    reasons = [item['reason'] for item in dataset['excluded']]
    assert reasons == ['evidence_reused_across_scopes', 'evidence_reused_across_scopes']
    assert dataset['episode_count'] == 0 and dataset['row_count'] == 0


def test_the_same_bytes_twice_in_one_scope_make_one_row(tmp_path):
    def build(samples):
        first = sample_folder(samples, 'first', scope='scope-a', name='Alpha Gift')
        sample_folder(samples, 'copy', scope='scope-a', name='Alpha Gift', reuse=first)
    dataset, _ = _dataset(tmp_path, ('copy', build))
    assert [item['reason'] for item in dataset['excluded']] == ['duplicate_evidence_in_one_scope']
    assert dataset['episode_count'] == 1 and dataset['row_count'] == 1


def test_a_verified_dataset_reports_what_it_verified(tmp_path):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    samples = tmp_path / 'samples'
    dataset = reviewed_episodes(samples, 10, catalogue=catalog_path)
    verification = dataset['verification']
    assert verification['verified'] is True
    assert verification['verified_episodes'] == 10 and verification['verified_rows'] == 10
    assert len(verification['dataset_sha256']) == 64
    assert all(len(row['content_address']) == 64 for row in verification['episodes'])
    assert dataset['ready'] is True


# ------------------------------------------------------------------ export

def _fitted_candidate(tmp_path, episodes):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    catalog = training.load_catalog(catalog_path)
    samples = tmp_path / 'samples'
    dataset = reviewed_episodes(samples, episodes, catalogue=catalog_path)
    rows = [row for episode in dataset['episodes'] for row in episode['rows']]
    fitted = training.fit(rows, epochs=20, seed=2)
    card = dict(training_ready=True, synthetic=False, production_enabled=False,
                reviewed_episodes=dataset['episode_count'],
                scopes=[episode['scope'] for episode in dataset['episodes']],
                verification=dataset['verification'],
                dataset_sha256=dataset['verification']['dataset_sha256'])
    return catalog, dataset, fitted, card


def test_export_writes_plain_json_with_production_disabled(tmp_path):
    catalog, dataset, fitted, card = _fitted_candidate(tmp_path, 10)
    result = training.export_candidate(fitted['parameters'], card, tmp_path / 'out',
                                       vocabulary=training.gift_vocabulary(catalog),
                                       keyword_vocabulary=training.keyword_vocabulary(catalog))
    assert result['production_enabled'] is False
    weights = json.loads(Path(result['weights']).read_text(encoding='utf-8'))
    modelcard = json.loads(Path(result['modelcard']).read_text(encoding='utf-8'))
    assert weights['production_enabled'] is False and modelcard['production_enabled'] is False
    assert modelcard['reviewed_episodes'] == 10
    assert json.loads(Path(result['weights']).read_text(encoding='utf-8')) == weights
    assert result['weights_sha256'] == modelcard['weights_sha256']


@pytest.mark.parametrize('episodes, patch, message', [
    (9, {}, 'fewer than 10 reviewed episodes'),
    (10, dict(synthetic=True), 'synthetic'),
    (10, dict(training_ready=False), 'not training ready'),
    (10, dict(production_enabled=True), 'production_enabled must be false'),
])
def test_export_refuses_a_candidate_it_must_not_write(tmp_path, episodes, patch, message):
    catalog, dataset, fitted, card = _fitted_candidate(tmp_path, episodes)
    card.update(patch)
    with pytest.raises(ValueError) as error:
        training.export_candidate(fitted['parameters'], card, tmp_path / 'out',
                                  vocabulary=training.gift_vocabulary(catalog),
                                  keyword_vocabulary=training.keyword_vocabulary(catalog))
    assert message in str(error.value)


def test_export_refuses_a_card_that_only_asserts_its_own_readiness(tmp_path):
    catalog, dataset, fitted, card = _fitted_candidate(tmp_path, 10)
    without = {key: value for key, value in card.items() if key != 'verification'}
    broken = [
        (without, 'no evidence verification summary'),
        (dict(card, verification=dict(card['verification'], verified=False)), 'not a verified one'),
        (dict(card, verification=dict(card['verification'], dataset_sha256='0' * 64)),
         'does not re-derive to its digest'),
        (dict(card, verification=dict(card['verification'], verified_episodes=3)),
         'fewer than 10 verified episodes'),
    ]
    for candidate, message in broken:
        with pytest.raises(ValueError) as error:
            training.export_candidate(fitted['parameters'], candidate, tmp_path / 'out',
                                      vocabulary=training.gift_vocabulary(catalog),
                                      keyword_vocabulary=training.keyword_vocabulary(catalog))
        assert message in str(error.value)
    assert not (tmp_path / 'out').exists()


def test_the_exported_modelcard_carries_the_evidence_it_was_trained_on(tmp_path):
    catalog, dataset, fitted, card = _fitted_candidate(tmp_path, 10)
    result = training.export_candidate(fitted['parameters'], card, tmp_path / 'out',
                                       vocabulary=training.gift_vocabulary(catalog),
                                       keyword_vocabulary=training.keyword_vocabulary(catalog))
    modelcard = json.loads(Path(result['modelcard']).read_text(encoding='utf-8'))
    assert modelcard['evidence_verified'] is True
    assert modelcard['dataset_sha256'] == dataset['verification']['dataset_sha256']
    assert modelcard['verification']['verified_rows'] == 10
    assert modelcard['production_enabled'] is False


def test_synthetic_rows_can_train_but_cannot_be_exported(tmp_path):
    catalog = training.load_catalog(REAL_CATALOG)
    vocabulary, keywords = training.gift_vocabulary(catalog), training.keyword_vocabulary(catalog)
    synthetic = training.synthetic_episodes(vocabulary, keywords, episodes=4, seed=1)
    rows = [row for episode in synthetic for row in episode['rows']]
    fitted = training.fit(rows, epochs=10, seed=1)
    assert fitted['metrics']['rows'] == 12
    with pytest.raises(ValueError):
        training.export_candidate(fitted['parameters'],
                                  dict(training_ready=True, synthetic=True, production_enabled=False,
                                       reviewed_episodes=99),
                                  tmp_path / 'out', vocabulary=vocabulary, keyword_vocabulary=keywords)


# ------------------------------------------------------------------ command line

def test_the_cli_reports_readiness_and_refuses_to_train_without_episodes(tmp_path):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    samples = tmp_path / 'samples'
    sample_folder(samples, 'pending', status='pending')
    tool = ROOT / 'tools/train_shop_value.py'
    report_only = subprocess.run([sys.executable, str(tool), '--samples', str(samples),
                                  '--catalog', str(catalog_path), '--out', str(tmp_path / 'out')],
                                 capture_output=True, text=True)
    assert report_only.returncode == 0
    assert json.loads(report_only.stdout)['report']['training_ready'] is False
    refused = subprocess.run([sys.executable, str(tool), '--samples', str(samples), '--train',
                              '--catalog', str(catalog_path), '--out', str(tmp_path / 'out')],
                             capture_output=True, text=True)
    assert refused.returncode == 3
    assert json.loads(refused.stdout)['kind'] == 'shop_value_training_refused'
    assert not (tmp_path / 'out').exists()


def test_the_cli_trains_and_labels_its_candidate_when_the_data_is_ready(tmp_path):
    catalog_path = tiny_catalog(tmp_path / 'gift-catalog.json')
    samples = tmp_path / 'samples'
    reviewed_episodes(samples, 12, catalogue=catalog_path)
    tool = ROOT / 'tools/train_shop_value.py'
    run = subprocess.run([sys.executable, str(tool), '--samples', str(samples), '--train',
                          '--catalog', str(catalog_path), '--out', str(tmp_path / 'out'),
                          '--ledger', str(ledger_for(samples)), '--epochs', '20'],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    payload = json.loads(run.stdout)
    assert payload['kind'] == 'shop_value_candidate'
    assert payload['exported']['production_enabled'] is False
    card = json.loads((tmp_path / 'out/modelcard.json').read_text(encoding='utf-8'))
    assert card['production_enabled'] is False and card['reviewed_episodes'] == 12
