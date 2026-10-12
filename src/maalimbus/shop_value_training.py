"""Offline shop-value model: pure encoding, a small NumPy MLP, plain-JSON export.

Nothing in this module touches a run.  It reads reviewed offline episodes, turns a
visible shop observation into numbers, fits a tiny network, and can export the
weights as plain JSON.  It never enables a policy: every artefact it writes says
``production_enabled: false`` and runtime ranking/promotion is somebody else's job.

Label rules the loader enforces, because they are the whole point of the dataset:

* a benefit label exists only where a human review approved the episode and gave a
  number for it (``review.json``), never from a self-label, a price, or an effect
  text;
* an executed purchase is labelled *execution*, so it is not by itself a positive
  sample and a success is never read as "a good buy";
* a gift that was *not* bought is not evidence of anything, so it never becomes a
  negative sample — such a row is excluded and counted, not zero-filled;
* one independent episode is one run scope; rows of a scope never straddle the
  train/test split.

No folder is trusted because it says so.  Before a folder may contribute a training
row, :func:`load_reviewed_episodes` re-reads its retained bytes through
:func:`verify_episode_evidence`: the folder name must be the content address of
``sample.json``, every ``before``/``after``/``question``/``notice`` proof must hash to
the bytes kept beside it, the exact coin delta and the complete shelf must be
re-derived from those frames, and the delayed ``outcome.json`` evidence must be
hash-bound to *this* scope by the run ledger and dated after the purchase.  That check
is read-only, always on, and has no off switch — a hand-edited sample, a swapped PNG, a
rewritten outcome, or evidence lifted from another journey is an exclusion reason, never
a row.

With fewer than :data:`MIN_REVIEWED_EPISODES` independent reviewed episodes the
honest output is a readiness report, not a model.
"""
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path

import numpy as np

FEATURE_SCHEMA = 1
MODEL_SCHEMA = 1
CARD_SCHEMA = 1
VERIFICATION_SCHEMA = 1
VERIFICATION_SOURCE = 'shop_value_training.evidence_verification'
MIN_REVIEWED_EPISODES = 10
PRODUCTION_ENABLED = False
DEFAULT_SAMPLES = 'build/learning-review/shop-purchases'
DEFAULT_CATALOG = 'assets/resource/base/gift-catalog.json'
DEFAULT_LEDGER = 'config/user-run-ledger.json'
DEFAULT_OUT = 'build/shop-value-model'

EVIDENCE_ROLES = ('before', 'after', 'question', 'notice')
REQUIRED_EVIDENCE_ROLES = ('before', 'after')

ACTIONS = ('buy', 'refresh', 'skip')
NUMERIC_FIELDS = ('price', 'coins', 'reserve_coins', 'floor', 'refreshes_used',
                  'refresh_limit', 'refresh_cost')
MASK_FIELDS = ('offer_name', 'keywords', 'owned', 'wanted') + NUMERIC_FIELDS
FLAG_FIELDS = ('known_gift', 'affordable', 'reserve_respected', 'refresh_room')
LABEL_SOURCE = 'human_reviewed_episode_benefit'


# --------------------------------------------------------------------------- catalogue

def load_catalog(path):
    """Read the gift catalogue whose names are the one-hot vocabulary."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('gifts'), list):
        raise ValueError('Gift catalogue needs version 1 and a gifts list')
    for entry in data['gifts']:
        if (not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not entry['name']
                or not isinstance(entry.get('keywords'), list)
                or any(not isinstance(item, str) or not item for item in entry['keywords'])):
            raise ValueError('Every catalogue gift needs a name and string keywords')
    return data


def gift_vocabulary(catalog):
    """The complete English gift names, sorted, one position each (no hashing)."""
    return tuple(sorted({entry['name'] for entry in catalog['gifts']}))


def keyword_vocabulary(catalog):
    """Every keyword any catalogue gift carries, sorted."""
    return tuple(sorted({item for entry in catalog['gifts'] for item in entry['keywords']}))


def feature_names(vocabulary, keyword_vocabulary):
    """The column order, so a reader can audit a vector without the encoder."""
    return (tuple('gift=%s' % name for name in vocabulary)
            + tuple('action=%s' % name for name in ACTIONS)
            + tuple('keyword=%s' % name for name in keyword_vocabulary)
            + tuple('value=%s' % name for name in NUMERIC_FIELDS)
            + tuple('mask=%s' % name for name in MASK_FIELDS)
            + tuple('flag=%s' % name for name in FLAG_FIELDS))


# --------------------------------------------------------------------------- encoding

def _optional_number(value, field, *, lower=0):
    if value is None:
        return None
    if type(value) is bool or not isinstance(value, (int, float)):
        raise ValueError('%s must be a number or null' % field)
    number = float(value)
    if not math.isfinite(number) or number < lower:
        raise ValueError('%s must be finite and >= %d' % (field, lower))
    return number


def _text_list(value, field):
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError('%s must be a list of non-empty strings' % field)
    return tuple(value)


def normalise_observation(observation):
    """Validate one visible observation and mark what is present.

    Missing fields stay ``None``; they are never guessed and never zero-filled
    silently — the mask block is what tells the model a value was absent.
    """
    if not isinstance(observation, dict):
        raise ValueError('A shop observation must be an object')
    action = observation.get('action')
    if action not in ACTIONS:
        raise ValueError('action must be one of %s' % (ACTIONS,))
    name = observation.get('offer_name')
    if name is not None and (not isinstance(name, str) or not name):
        raise ValueError('offer_name must be a non-empty string or null')
    return dict(
        action=action,
        offer_name=name,
        price=_optional_number(observation.get('price'), 'price'),
        coins=_optional_number(observation.get('coins'), 'coins'),
        reserve_coins=_optional_number(observation.get('reserve_coins'), 'reserve_coins'),
        floor=_optional_number(observation.get('floor'), 'floor'),
        refreshes_used=_optional_number(observation.get('refreshes_used'), 'refreshes_used'),
        refresh_limit=_optional_number(observation.get('refresh_limit'), 'refresh_limit'),
        refresh_cost=_optional_number(observation.get('refresh_cost'), 'refresh_cost'),
        keywords=_text_list(observation.get('keywords'), 'keywords'),
        owned=_text_list(observation.get('owned'), 'owned'),
        wanted=_text_list(observation.get('wanted'), 'wanted'),
    )


def encode_observation(observation, *, vocabulary, keyword_vocabulary):
    """One observation -> fixed-width floats plus its missing mask.

    The order is exactly :func:`feature_names`: gift one-hot, action one-hot,
    keyword one-hot, normalised visible numbers, present/absent mask, and the
    feasibility flags.  An unknown gift name contributes no one-hot position and
    only clears ``known_gift``; it is never folded onto a similar name.
    """
    obs = normalise_observation(observation)
    known = {name: index for index, name in enumerate(vocabulary)}
    keywords = {name: index for index, name in enumerate(keyword_vocabulary)}

    values = [0.0] * len(vocabulary)
    known_gift = 0.0
    if obs['offer_name'] is not None and obs['offer_name'] in known:
        values[known[obs['offer_name']]] = 1.0
        known_gift = 1.0

    action = [0.0] * len(ACTIONS)
    action[ACTIONS.index(obs['action'])] = 1.0
    values[len(vocabulary):len(vocabulary) + len(ACTIONS)] = action

    keyword_block = [0.0] * len(keyword_vocabulary)
    if obs['keywords'] is not None:
        for item in obs['keywords']:
            if item in keywords:
                keyword_block[keywords[item]] = 1.0
    base = len(vocabulary) + len(ACTIONS)
    values[base:base + len(keyword_vocabulary)] = keyword_block

    coins = obs['coins']
    numbers = []
    for field in NUMERIC_FIELDS:
        number = obs[field]
        if number is None:
            numbers.append(0.0)
        elif field in ('coins',):
            numbers.append(min(number / 1000.0, 1.0))
        elif field == 'floor':
            numbers.append(min(number / 5.0, 1.0))
        elif field in ('reserve_coins', 'price', 'refresh_cost'):
            numbers.append(min(number / coins, 1.0) if coins else 0.0)
        elif field == 'refreshes_used':
            limit = obs['refresh_limit']
            numbers.append(min(number / limit, 1.0) if limit else 0.0)
        else:
            numbers.append(min(number / 4.0, 1.0))
    base += len(keyword_vocabulary)
    values[base:base + len(NUMERIC_FIELDS)] = numbers

    mask = []
    for field in MASK_FIELDS:
        if field in ('offer_name', 'keywords', 'owned', 'wanted'):
            mask.append(1.0 if obs[field] not in (None, ()) else 0.0)
        else:
            mask.append(1.0 if obs[field] is not None else 0.0)
    base += len(NUMERIC_FIELDS)
    values[base:base + len(MASK_FIELDS)] = mask

    spendable = None if coins is None else coins - (obs['reserve_coins'] or 0.0)
    flags = [
        known_gift,
        1.0 if (spendable is not None and obs['price'] is not None and obs['price'] <= spendable) else 0.0,
        1.0 if (spendable is None or obs['price'] is None or obs['price'] <= spendable) else 0.0,
        1.0 if (obs['refreshes_used'] is not None and obs['refresh_limit'] is not None
                and obs['refreshes_used'] < obs['refresh_limit']) else 0.0,
    ]
    base += len(MASK_FIELDS)
    values[base:base + len(FLAG_FIELDS)] = flags

    names = feature_names(vocabulary, keyword_vocabulary)
    if len(values) != len(names):
        raise AssertionError('encoder width %d does not match %d feature names' % (len(values), len(names)))
    return dict(schema_version=FEATURE_SCHEMA, values=values, mask=mask, feature_names=names,
                width=len(values), known_gift=bool(known_gift), action=obs['action'])


def sample_observation(sample):
    """The visible observation a reviewed purchase sample carries.

    Only fields the sample really holds come through; the rest stay absent so the
    mask records the gap instead of a manufactured value.
    """
    context = sample.get('context') or {}
    return normalise_observation(dict(
        action='buy',
        offer_name=sample.get('name'),
        price=sample.get('price'),
        coins=sample.get('coins_before'),
        reserve_coins=context.get('reserve_coins'),
        floor=context.get('floor'),
        refreshes_used=context.get('refreshes_used'),
        refresh_limit=context.get('refresh_limit'),
        refresh_cost=context.get('refresh_cost'),
        keywords=context.get('keywords'),
        owned=context.get('owned_bought'),
        wanted=context.get('wanted'),
    ))


# --------------------------------------------------------------------------- dataset

def _load_json(path):
    """Read one JSON object, or name the reason it is not one.

    A missing file, unreadable bytes, malformed JSON, or a non-object top level is a
    per-sample exclusion reason: the readiness report is what a reviewer reads, so one
    broken folder must never take the whole report down.
    """
    try:
        text = Path(path).read_text(encoding='utf-8')
    except FileNotFoundError:
        return None, 'missing'
    except UnicodeDecodeError as error:
        return None, 'not_utf8: %s' % error
    except OSError as error:
        return None, 'unreadable: %s' % error
    try:
        data = json.loads(text)
    except ValueError as error:
        return None, 'malformed: %s' % error
    if not isinstance(data, dict):
        return None, 'not_an_object'
    return data, None


def _exclude(key, reason):
    return dict(sample=key, reason=reason)


# --------------------------------------------------------------------------- evidence

def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _is_digest(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _path_key(path):
    return str(Path(path))


def _later(value, base):
    """A delayed consequence carries a timezone-bound moment after the purchase."""
    try:
        moment, start = datetime.fromisoformat(value), datetime.fromisoformat(base)
    except (TypeError, ValueError):
        return False
    if moment.tzinfo is None or start.tzinfo is None:
        return False
    return moment > start


def _frame_reading(folder, role):
    """Re-read one retained frame pair with the repository's own frame reader."""
    from .shop_transaction import _frame
    try:
        record, texts, size, proof = _frame(Path(folder) / (role + '.json'))
    except (ValueError, OSError) as error:
        return None, 'evidence_%s_unreadable: %s' % (role, error)
    return dict(record=record, texts=texts, size=size, json_sha256=proof['json_sha256'],
                png_sha256=proof['png_sha256']), None


def _purchase_rule(sample, before, after):
    """Re-derive the exact spend and the complete shelf from the retained frames.

    This is the same rule the transaction store used to accept the purchase, re-run
    here over the retained bytes: one high-confidence currency, the bought name at the
    recorded price and not already marked purchased, ``after`` exactly ``price`` coins
    poorer, and every other offer unchanged.
    """
    from .shop_transaction import _coins, _key, _shelf
    if before['record'].get('scene') != 'SHOP' or after['record'].get('scene') != 'SHOP':
        return 'purchase_frames_are_not_the_shop'
    try:
        prior = _shelf(before['texts'], before['size'])
        following = _shelf(after['texts'], after['size'])
        coins_before = _coins(before['texts'], before['size'])
        coins_after = _coins(after['texts'], after['size'])
    except ValueError as error:
        return 'shop_reading_failed: %s' % error
    price, name = sample['price'], sample['name']
    chosen = [offer for offer in prior if _key(offer['name']) == _key(name)]
    kept = [offer for offer in following if _key(offer['name']) == _key(name)]
    others = lambda rows: sorted((_key(offer['name']), offer['price']) for offer in rows
                                 if _key(offer['name']) != _key(name))
    if (len(chosen) != 1 or chosen[0]['price'] != price or chosen[0].get('purchased')
            or coins_before != sample['coins_before'] or coins_after != sample['coins_after']
            or coins_after != coins_before - price or others(prior) != others(following)
            or (kept and (len(kept) != 1 or not kept[0].get('purchased') or kept[0]['price'] != price))):
        return 'purchase_evidence_differs_from_the_sample'
    return None


def _resolve_ledger(ledger):
    """The run ledger that binds a scope to its evidence, or why it is unusable."""
    if ledger is None:
        return None, 'run_ledger_absent'
    if isinstance(ledger, dict):
        return ledger, None
    data, problem = _load_json(ledger)
    if data is None:
        return None, 'run_ledger_%s' % problem
    if data.get('version') != 1:
        return None, 'run_ledger_version_differs'
    return data, None


def _scope_evidence(ledger, scope):
    """Every piece of evidence the ledger binds to this scope."""
    runs = [run for run in [ledger.get('active'), *(ledger.get('receipts')
            if isinstance(ledger.get('receipts'), list) else [])]
            if isinstance(run, dict) and run.get('id') == scope]
    if len(runs) > 1:
        return None, 'run_ledger_scope_ambiguous'
    if not runs:
        return None, 'delayed_outcome_scope_not_in_run_ledger'
    bound = {}
    for event in (runs[0].get('events') or {}).values():
        if (isinstance(event, dict) and isinstance(event.get('evidence'), str)
                and _is_digest(event.get('sha256'))):
            bound[_path_key(event['evidence'])] = event['sha256']
    return bound, None


def _outcome_rule(folder, outcome, sample, before, ledger, ledger_problem):
    """The delayed evidence must be hash-bound to this scope and dated after it."""
    if outcome.get('human_approved') is not True:
        return 'outcome_not_human_approved', None
    if outcome.get('training_eligible') is not True:
        return 'outcome_not_training_eligible', None
    if ledger is None:
        return ledger_problem, None
    bound, problem = _scope_evidence(ledger, sample.get('scope'))
    if bound is None:
        return problem, None
    entries = outcome.get('outcomes')
    if not isinstance(entries, list) or not entries:
        return 'delayed_outcome_evidence_missing', None
    digests, context = [], before['record'].get('utc')
    for entry in entries:
        event = entry.get('evidence') if isinstance(entry, dict) else None
        digest = event.get('sha256') if isinstance(event, dict) else None
        path = event.get('evidence') if isinstance(event, dict) else None
        image = entry.get('image_sha256') if isinstance(entry, dict) else None
        if not _is_digest(digest) or not isinstance(path, str) or not path or not _is_digest(image):
            return 'delayed_outcome_evidence_invalid', None
        if bound.get(_path_key(path)) != digest:
            return 'delayed_outcome_not_bound_to_the_scope', None
        copy = folder / ('outcome-' + digest)
        if not (copy.with_suffix('.json').exists() and copy.with_suffix('.png').exists()):
            return 'delayed_outcome_copy_missing', None
        if _sha256_file(copy.with_suffix('.json')) != digest:
            return 'delayed_outcome_json_hash_differs', None
        if _sha256_file(copy.with_suffix('.png')) != image:
            return 'delayed_outcome_png_hash_differs', None
        record, reason = _load_json(copy.with_suffix('.json'))
        if record is None:
            return 'delayed_outcome_%s' % reason, None
        if record.get('image_sha256') != image:
            return 'delayed_outcome_png_hash_differs', None
        if not _later(record.get('utc'), context):
            return 'delayed_outcome_not_later_than_the_purchase', None
        digests.append(digest)
    return None, digests


def verify_episode_evidence(folder, sample, outcome, *, ledger=None, ledger_problem=None):
    """Re-read the retained bytes and re-derive what the sample claims they prove.

    Read-only by construction: nothing here writes, copies, or repairs, and there is no
    way to switch it off.  It runs for every folder before a training row may exist, so
    a hand-edited ``sample.json``, a swapped PNG, a rewritten ``outcome.json``, or
    evidence lifted from another journey is an exclusion reason instead of a row.
    """
    folder, ledger = Path(folder), (ledger if isinstance(ledger, dict) else None)
    try:
        address = hashlib.sha256(json.dumps(sample, sort_keys=True).encode('utf-8')).hexdigest()
    except (TypeError, ValueError):
        return _unverified('sample_content_address_uncomputable')
    if address != folder.name:
        return _unverified('sample_content_address_differs', content_address=address)
    if type(sample.get('price')) is not int or sample['price'] < 0:
        return _unverified('sample_price_invalid', content_address=address)
    if not isinstance(sample.get('name'), str) or not sample['name']:
        return _unverified('sample_name_invalid', content_address=address)
    if type(sample.get('coins_before')) is not int or type(sample.get('coins_after')) is not int:
        return _unverified('sample_coins_invalid', content_address=address)
    readings, hashes = {}, {}
    for role in EVIDENCE_ROLES:
        proof = sample.get(role)
        if proof is None:
            if role in REQUIRED_EVIDENCE_ROLES:
                return _unverified('evidence_%s_missing' % role, content_address=address)
            continue
        if (not isinstance(proof, dict) or not isinstance(proof.get('path'), str) or not proof['path']
                or not _is_digest(proof.get('json_sha256')) or not _is_digest(proof.get('png_sha256'))):
            return _unverified('evidence_%s_proof_invalid' % role, content_address=address)
        reading, problem = _frame_reading(folder, role)
        if reading is None:
            return _unverified(problem, content_address=address)
        if (reading['json_sha256'] != proof['json_sha256']
                or reading['png_sha256'] != proof['png_sha256']):
            return _unverified('evidence_%s_hash_differs' % role, content_address=address)
        readings[role] = reading
        hashes[role] = dict(json_sha256=reading['json_sha256'], png_sha256=reading['png_sha256'])
    problem = _purchase_rule(sample, readings['before'], readings['after'])
    if problem:
        return _unverified(problem, content_address=address, hashes=hashes)
    problem, digests = _outcome_rule(folder, outcome, sample, readings['before'], ledger, ledger_problem)
    if problem:
        return _unverified(problem, content_address=address, hashes=hashes)
    return dict(verified=True, reason=None, content_address=address, hashes=hashes,
                outcome_sha256=digests, scope=sample.get('scope'))


def _unverified(reason, **extra):
    return dict(verified=False, reason=reason, content_address=extra.get('content_address'),
                hashes=extra.get('hashes') or {}, outcome_sha256=[])


def _verification_digest(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode('utf-8')).hexdigest()


def verification_summary(episodes, *, excluded=()):
    """The evidence hashes a modelcard must carry, under one re-computable digest."""
    entries = []
    for episode in episodes:
        for row in episode['rows']:
            evidence = row['evidence']
            entries.append(dict(scope=row['scope'], sample=row['sample'],
                                content_address=evidence['content_address'],
                                hashes=evidence['hashes'],
                                outcome_sha256=list(evidence['outcome_sha256'])))
    return dict(schema_version=VERIFICATION_SCHEMA, source=VERIFICATION_SOURCE, verified=True,
                verified_episodes=len(episodes), verified_rows=len(entries), episodes=entries,
                dataset_sha256=_verification_digest(entries),
                excluded=[dict(sample=item['sample'], reason=item['reason']) for item in excluded])


def load_reviewed_episodes(root, catalog, *, min_episodes=MIN_REVIEWED_EPISODES,
                           ledger=DEFAULT_LEDGER):
    """Join the reviewed sample folders into scope-keyed episodes, or say why not.

    Every folder under ``root`` is inspected; a folder that cannot supply a
    human-approved benefit label *and* survive :func:`verify_episode_evidence` is
    excluded with a reason.  Nothing is inferred: the returned ``ready`` flag and its
    :func:`verification_summary` are the only gate training may consult.
    """
    root = Path(root)
    gift_names = gift_vocabulary(catalog)
    keyword_names = keyword_vocabulary(catalog)
    ledger_state, ledger_problem = _resolve_ledger(ledger)
    by_scope, excluded, seen, statuses = {}, [], 0, {}
    first_use, conflicted = {}, set()
    if root.is_dir():
        for folder in sorted(path for path in root.iterdir() if path.is_dir()):
            key = folder.name
            seen += 1
            sample, problem = _load_json(folder / 'sample.json')
            if sample is None:
                excluded.append(_exclude(key, 'sample_missing_or_unreadable'
                                         if problem == 'missing' else 'sample_%s' % problem))
                continue
            if sample.get('version') != 1 or sample.get('kind') != 'purchase_outcome':
                excluded.append(_exclude(key, 'sample_shape_unknown'))
                continue
            review, problem = _load_json(folder / 'review.json')
            if review is None:
                excluded.append(_exclude(key, 'review_missing'
                                         if problem == 'missing' else 'review_%s' % problem))
                continue
            status = review.get('status')
            statuses[status] = statuses.get(status, 0) + 1
            if status == 'rejected':
                excluded.append(_exclude(key, 'review_rejected'))
                continue
            if status != 'approved':
                excluded.append(_exclude(key, 'review_not_approved'))
                continue
            if sample.get('action_executed') is not True:
                # An offer nobody bought is not evidence; it must never become a 0.
                excluded.append(_exclude(key, 'no_purchase_is_not_a_negative_sample'))
                continue
            outcome, problem = _load_json(folder / 'outcome.json')
            if outcome is None or outcome.get('training_eligible') is not True:
                excluded.append(_exclude(key, 'outcome_not_training_eligible'))
                continue
            benefit = review.get('benefit')
            if benefit is None:
                excluded.append(_exclude(key, 'benefit_label_absent'))
                continue
            if type(benefit) is bool or not isinstance(benefit, (int, float)) or not 0.0 <= float(benefit) <= 1.0:
                excluded.append(_exclude(key, 'benefit_label_not_a_0..1_number'))
                continue
            scope = sample.get('scope')
            if not isinstance(scope, str) or not scope:
                excluded.append(_exclude(key, 'scope_absent'))
                continue
            evidence = verify_episode_evidence(folder, sample, outcome, ledger=ledger_state,
                                               ledger_problem=ledger_problem)
            if not evidence['verified']:
                excluded.append(_exclude(key, evidence['reason']))
                continue
            # One purchase's bytes cannot honestly be two independent episodes.
            fingerprint = (evidence['hashes']['before']['json_sha256'],
                           evidence['hashes']['after']['json_sha256'])
            owner = first_use.get(fingerprint)
            if owner is not None:
                if owner[1] == scope:
                    # Two folders, one purchase: the second is not a second row.
                    excluded.append(_exclude(key, 'duplicate_evidence_in_one_scope'))
                    continue
                conflicted.update((owner[0], key))
                excluded.append(_exclude(key, 'evidence_reused_across_scopes'))
                excluded.append(_exclude(owner[0], 'evidence_reused_across_scopes'))
                continue
            first_use.setdefault(fingerprint, (key, scope))
            try:
                observation = sample_observation(sample)
            except ValueError as error:
                excluded.append(_exclude(key, 'observation_invalid: %s' % error))
                continue
            encoded = encode_observation(observation, vocabulary=gift_names,
                                         keyword_vocabulary=keyword_names)
            by_scope.setdefault(scope, []).append(dict(
                sample=key, scope=scope, values=encoded['values'], target=float(benefit),
                observation=observation, action=observation['action'],
                evidence=evidence, label_source=LABEL_SOURCE))
    if conflicted:
        for scope in list(by_scope):
            by_scope[scope] = [row for row in by_scope[scope] if row['sample'] not in conflicted]
            if not by_scope[scope]:
                del by_scope[scope]
    episodes = [dict(scope=scope, rows=rows) for scope, rows in sorted(by_scope.items())]
    blockers = []
    if len(episodes) < min_episodes:
        blockers.append('reviewed_episodes %d < required %d' % (len(episodes), min_episodes))
    if root.is_dir() and not episodes and seen:
        blockers.append('no folder carries a verified approved review with a benefit label')
    if not root.is_dir():
        blockers.append('sample root %s does not exist' % root)
    return dict(root=str(root), samples_seen=seen, review_status_counts=statuses,
                episodes=episodes, excluded=excluded, episode_count=len(episodes),
                row_count=sum(len(episode['rows']) for episode in episodes),
                verification=verification_summary(episodes, excluded=excluded),
                min_episodes=min_episodes, ready=not blockers, blockers=blockers,
                label_source=LABEL_SOURCE)


def readiness_report(root, catalog, *, min_episodes=MIN_REVIEWED_EPISODES, ledger=DEFAULT_LEDGER):
    """What can honestly be said about training right now."""
    dataset = load_reviewed_episodes(root, catalog, min_episodes=min_episodes, ledger=ledger)
    reasons = {}
    for item in dataset['excluded']:
        reasons[item['reason']] = reasons.get(item['reason'], 0) + 1
    return dict(
        kind='shop_value_readiness',
        schema_version=1,
        production_enabled=PRODUCTION_ENABLED,
        samples_root=dataset['root'],
        samples_seen=dataset['samples_seen'],
        review_status_counts=dataset['review_status_counts'],
        exclusion_reasons=reasons,
        reviewed_episodes=dataset['episode_count'],
        reviewed_rows=dataset['row_count'],
        verification_schema=VERIFICATION_SCHEMA,
        verified_rows=dataset['verification']['verified_rows'],
        dataset_sha256=dataset['verification']['dataset_sha256'],
        scopes=[episode['scope'] for episode in dataset['episodes']],
        min_episodes=min_episodes,
        training_ready=dataset['ready'],
        blockers=dataset['blockers'],
        label_source=LABEL_SOURCE,
        next_actions=[
            'review each sample folder: set review.json status=approved and a benefit in 0..1',
            'attach a training-eligible outcome.json whose delayed evidence the run ledger binds to its scope',
            'keep the evidence bytes beside each sample: verification re-reads them and cannot be turned off',
            'collect independent scopes until %d verified episodes exist' % min_episodes,
        ],
        not_a_model=True,
    )


def split_by_scope(episodes, *, test_fraction=0.3, seed=7):
    """Split whole scopes; neighbouring frames of one run never straddle the cut."""
    if not 0.0 <= test_fraction < 1.0:
        raise ValueError('test_fraction must be in 0..1')
    ordered = sorted(episodes, key=lambda episode: episode['scope'])
    rng = np.random.default_rng(seed)
    shuffled = list(ordered)
    rng.shuffle(shuffled)
    if len(shuffled) < 2:
        return list(ordered), []
    cut = max(1, int(round(len(shuffled) * test_fraction)))
    cut = min(cut, len(shuffled) - 1)
    test = sorted(shuffled[:cut], key=lambda episode: episode['scope'])
    train = sorted(shuffled[cut:], key=lambda episode: episode['scope'])
    return train, test


# --------------------------------------------------------------------------- model

def init_parameters(width, hidden, seed):
    """Small deterministic weights; the only randomness is the seed."""
    if width < 1 or hidden < 1:
        raise ValueError('width and hidden must be positive')
    rng = np.random.default_rng(seed)
    return dict(
        w1=(rng.standard_normal((hidden, width)) / math.sqrt(width)).tolist(),
        b1=[0.0] * hidden,
        w2=(rng.standard_normal(hidden) / math.sqrt(hidden)).tolist(),
        b2=0.0,
    )


def _arrays(parameters):
    return (np.asarray(parameters['w1'], dtype=float), np.asarray(parameters['b1'], dtype=float),
            np.asarray(parameters['w2'], dtype=float), float(parameters['b2']))


def _forward_arrays(w1, b1, w2, b2, matrix):
    hidden = np.tanh(matrix @ w1.T + b1)
    logits = hidden @ w2 + b2
    return hidden, 1.0 / (1.0 + np.exp(-logits))


def forward(parameters, values):
    """One vector -> the model's value in 0..1 (a ranking signal, not a price)."""
    w1, b1, w2, b2 = _arrays(parameters)
    _, output = _forward_arrays(w1, b1, w2, b2, np.asarray([list(values)], dtype=float))
    return float(output[0])


def fit(rows, *, hidden=8, epochs=400, learning_rate=0.05, seed=7, l2=1e-4, momentum=0.9):
    """Fit the tiny MLP on encoded rows; returns plain lists and a loss history."""
    if not rows:
        raise ValueError('Training needs at least one row')
    matrix = np.asarray([row['values'] for row in rows], dtype=float)
    targets = np.asarray([float(row['target']) for row in rows], dtype=float)
    parameters = init_parameters(matrix.shape[1], hidden, seed)
    w1, b1, w2, b2 = _arrays(parameters)
    velocity = {name: np.zeros_like(value) for name, value in
                (('w1', w1), ('b1', b1), ('w2', w2), ('b2', np.asarray(b2)))}
    history = []
    for _ in range(max(1, epochs)):
        hidden_values, output = _forward_arrays(w1, b1, w2, b2, matrix)
        loss = float(np.mean((output - targets) ** 2))
        history.append(loss)
        delta = (2.0 / len(targets)) * (output - targets) * output * (1.0 - output)
        grad_w2 = hidden_values.T @ delta + l2 * w2
        grad_b2 = float(delta.sum())
        grad_hidden = np.outer(delta, w2) * (1.0 - hidden_values ** 2)
        grad_w1 = grad_hidden.T @ matrix + l2 * w1
        grad_b1 = grad_hidden.sum(axis=0)
        for name, gradient in (('w1', grad_w1), ('b1', grad_b1), ('w2', grad_w2), ('b2', np.asarray(grad_b2))):
            velocity[name] = momentum * velocity[name] - learning_rate * gradient
        w1 = w1 + velocity['w1']
        b1 = b1 + velocity['b1']
        w2 = w2 + velocity['w2']
        b2 = float(b2 + velocity['b2'])
    fitted = dict(w1=w1.tolist(), b1=b1.tolist(), w2=w2.tolist(), b2=b2)
    predictions = [forward(fitted, row['values']) for row in rows]
    return dict(parameters=fitted, width=matrix.shape[1], hidden=hidden, epochs=max(1, epochs),
                learning_rate=learning_rate, l2=l2, seed=seed,
                history=[round(value, 8) for value in history],
                metrics=dict(loss_start=round(history[0], 8), loss_end=round(history[-1], 8),
                             rows=len(rows), **pairwise_accuracy(predictions, targets.tolist())))


def pairwise_accuracy(predictions, targets):
    """How often the prediction orders two rows the way the labels do (ties skip)."""
    pairs = right = 0
    for left in range(len(predictions)):
        for right_index in range(left + 1, len(predictions)):
            if targets[left] == targets[right_index]:
                continue
            pairs += 1
            higher = predictions[left] - predictions[right_index]
            if (higher > 0) == (targets[left] > targets[right_index]) and higher != 0:
                right += 1
    return dict(pairs=pairs, pairwise_accuracy=(right / pairs) if pairs else None)


# --------------------------------------------------------------------------- export

def _weights_payload(parameters, vocabulary, keyword_vocabulary):
    names = feature_names(vocabulary, keyword_vocabulary)
    return dict(schema_version=MODEL_SCHEMA, kind='shop_value_weights', feature_schema=FEATURE_SCHEMA,
                production_enabled=False, input_width=len(names), hidden=len(parameters['w2']),
                activation='tanh', output='sigmoid', vocabulary=list(vocabulary),
                keyword_vocabulary=list(keyword_vocabulary), feature_names=list(names),
                parameters={key: (value if isinstance(value, list) else float(value))
                            for key, value in parameters.items()})


def export_candidate(parameters, modelcard, directory, *, vocabulary, keyword_vocabulary):
    """Write weights.json + modelcard.json — plain JSON only, never pickle.

    Refuses unless a real, reviewed, sufficient dataset produced the model: a
    candidate made from synthetic rows or from too few episodes does not exist as
    an artefact, because a file on disk is what a runtime would otherwise pick up.
    """
    card = dict(modelcard)
    if card.get('training_ready') is not True:
        raise ValueError('Refusing to export: the dataset is not training ready')
    if card.get('synthetic') is True:
        raise ValueError('Refusing to export: synthetic rows may only exercise the trainer')
    if int(card.get('reviewed_episodes', 0)) < MIN_REVIEWED_EPISODES:
        raise ValueError('Refusing to export: fewer than %d reviewed episodes' % MIN_REVIEWED_EPISODES)
    # A caller may not assert readiness: the card must carry a verification summary that
    # re-derives to the digest it claims, produced by verify_episode_evidence.
    verification = card.get('verification')
    if not isinstance(verification, dict):
        raise ValueError('Refusing to export: the modelcard carries no evidence verification summary')
    if (verification.get('schema_version') != VERIFICATION_SCHEMA
            or verification.get('source') != VERIFICATION_SOURCE
            or verification.get('verified') is not True):
        raise ValueError('Refusing to export: the evidence verification summary is not a verified one')
    if not _is_digest(verification.get('dataset_sha256')):
        raise ValueError('Refusing to export: the evidence summary carries no dataset digest')
    if _verification_digest(verification.get('episodes') or []) != verification['dataset_sha256']:
        raise ValueError('Refusing to export: the evidence summary does not re-derive to its digest')
    if int(verification.get('verified_episodes') or 0) < MIN_REVIEWED_EPISODES:
        raise ValueError('Refusing to export: fewer than %d verified episodes' % MIN_REVIEWED_EPISODES)
    if card.get('production_enabled') is not False:
        raise ValueError('Refusing to export: production_enabled must be false')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    payload = _weights_payload(parameters, vocabulary, keyword_vocabulary)
    payload['dataset_sha256'] = verification['dataset_sha256']
    card.update(schema_version=CARD_SCHEMA, kind='shop_value_modelcard', feature_schema=FEATURE_SCHEMA,
                production_enabled=False, weights_sha256=None,
                # Recorded from the verified summary, not from anything a caller passed.
                evidence_verified=True, dataset_sha256=verification['dataset_sha256'],
                verified_episodes=verification['verified_episodes'],
                verified_rows=verification['verified_rows'], verification=verification)
    body = json.dumps(payload, sort_keys=True).encode('utf-8')
    card['weights_sha256'] = hashlib.sha256(body).hexdigest()
    weights_path, card_path = directory / 'weights.json', directory / 'modelcard.json'
    weights_path.write_bytes(body)
    card_path.write_text(json.dumps(card, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
    return dict(schema_version=CARD_SCHEMA, production_enabled=False, weights=str(weights_path),
                modelcard=str(card_path), weights_sha256=card['weights_sha256'])


# --------------------------------------------------------------------------- synthetic

def synthetic_episodes(vocabulary, keyword_vocabulary, *, episodes=12, seed=7):
    """Deterministic rows that exist only to exercise the trainer in tests.

    They carry ``synthetic`` provenance all the way into the modelcard, and
    :func:`export_candidate` refuses them: they may never be mistaken for data.
    """
    rng = np.random.default_rng(seed)
    names = list(vocabulary)
    keywords = list(keyword_vocabulary)
    made = []
    for index in range(episodes):
        rows = []
        for _ in range(3):
            good = bool(rng.integers(0, 2))
            name = names[int(rng.integers(0, len(names)))] if names else None
            keyword = keywords[int(rng.integers(0, len(keywords)))] if keywords else None
            observation = dict(action='buy', offer_name=name,
                               price=int(120 if good else 260), coins=1000,
                               reserve_coins=0, floor=2, refreshes_used=0, refresh_limit=2,
                               refresh_cost=None, keywords=[keyword] if keyword else [],
                               owned=[], wanted=[])
            encoded = encode_observation(observation, vocabulary=vocabulary,
                                        keyword_vocabulary=keyword_vocabulary)
            rows.append(dict(sample='synthetic-%d-%d' % (index, len(rows)), scope='synthetic-%d' % index,
                             values=encoded['values'], target=0.9 if good else 0.2,
                             observation=observation, action='buy', label_source='synthetic_test_row'))
        made.append(dict(scope='synthetic-%d' % index, rows=rows))
    return made
