"""Offline, auditable Mirror decision policy: static heuristics plus a bounded learned term.

What this module is
-------------------
A pure, side-effect-free scoring policy for the Mirror Dungeon decisions that the runner
already reads from frames: which predicted reward to take, which node to walk to, whether a
shop offer is worth its in-run price, and whether a bounded skill replacement may proceed.
Nothing here reads a file, opens a device, sends input, touches a ledger or a budget, starts
a game, or trains a model. Every function is total over its documented input domain and
raises ValueError on evidence it cannot audit; a refusal is always a reported reason, never a
guessed number.

Two scores, never one
---------------------
Every decision is reported as two separated components:

* ``static`` -- an editable heuristic weight from an explicit table. These are preference
  orderings. They are not the game's internal numbers and they are not a claimed optimal
  strategy. docs/design.md already fixes that posture for gift trials and route kinds, and
  assets/resource/base/route-policy.json says the same thing about its own weights.
* ``learned`` -- a bounded adjustment derived only from outcomes that carry eligibility. The
  module never invents a learned number: with no eligible outcome, or when the caller's
  knowledge base is empty, ``learned`` is exactly 0.0 and the result says so
  (``learned_applied: False``, ``learned_reason: 'no_eligible_episodes'``).

``model_trained`` is False in every result and in ``policy_summary``: tallying episode
outcomes is not training a model, and this module must never be read as claiming one exists.

Evidence posture
----------------
* Gift, route and shop scores only order options that an independent reader already produced.
  They never prove a node identity, an offer name, a gift identity or a balance.
* The shop never scores a purchase from a made-up price: currency, price and the offer set
  come from the caller, and a non-integer price or an over-balance price refuses.
* A skill replacement is a *bounded* decision. It requires a known sinner, a skill id that
  the loaded identity catalog already binds to that sinner, a complete (untruncated) caption
  read from the page, an integer price inside the run currency, and the skill that the
  replacement displaces. Any missing or unreadable element -- including an unknown question --
  returns ``refused: True`` with a named reason. There is no fallback branch that acts.
* ``strategy_training_eligible`` is the only gate that admits an outcome into the learned
  aggregate, so the censored completion-only assessment from ``mirror_assessment`` (which
  reports ``strategy_training_eligible: False``) can never quietly become learned evidence.

Catalog shape
-------------
``load_identity_catalog`` validates the shipped
``assets/resource/base/identity-catalog.json`` shape (or any fixture with the same shape). It
is the only place that touches a file, it is read-only, and it never copies account data,
screenshots, logs or private configuration anywhere.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

# --------------------------------------------------------------------------------------
# Version and fixed vocabularies
# --------------------------------------------------------------------------------------

POLICY_VERSION = 1
CENSOR_PRIOR_PROBABILITY = 0.5

GIFT_SCORE_VERSION = 1
ROUTE_SCORE_VERSION = 1
SHOP_SCORE_VERSION = 1
SKILL_REPLACEMENT_VERSION = 1

DECISION_KINDS = ('gift', 'route', 'shop', 'skill_replacement')
ROUTE_KINDS = ('abnormality', 'boss', 'elite', 'empty', 'event', 'focused', 'regular', 'shop')
PLACEMENTS = ('left', 'middle', 'right')

#: Editable heuristic weights, one explicit table. They order options a reader already
#: recognised; they are not game formulas. Gift values are pre-image tie-breakers only --
#: the live image wins whenever one is supplied.
DEFAULT_STATIC = {
    'gift_base': 100.0,
    'gift_owned': 2.0,
    'gift_preference': 8.0,
    'gift_learning_gain': 60.0,
    'trial_weight': 1.0,
    'route_base': 1.0,
    'route_weight': 0.5,
    'shop_offer_base': 100.0,
    'shop_keyword': 24.0,
    'shop_duplicate': -200.0,
    'shop_learning_gain': 60.0,
    'shop_fusion_bonus': 25.0,
    'shop_health_risk': 12.0,
    'skill_buff_weight': 10.0,
    'skill_base_weight': 18.0,
}

#: Route kind weights, mirroring assets/resource/base/route-policy.json so a caller that
#: wants the shipped table can pass it in as ``weights`` and get byte-equal ordering.
ROUTE_KIND_WEIGHTS = {
    'abnormality': 1.8,
    'boss': 3.0,
    'elite': 2.4,
    'empty': 0.2,
    'event': 1.6,
    'focused': 2.2,
    'regular': 1.4,
    'shop': 1.2,
}

#: The bounded learned term. ``rate`` is expected points per event normalised by the prior
#: mean, clamped to +/-1; the gain scales it and the cap bounds the whole adjustment, so no
#: single episode can run the score away.
LEARNED_GAIN = 1.0
LEARNED_RATE_CAP = 1.0
LEARNED_ADJUST_CAP = 2.0
LEARNED_MIN_EVENTS = 1

_TRUNCATION_MARKERS = ('...', '\u2026', '\u22ef', '..')

#: Distinguishes "the caller measured nothing" from "the caller passed a bad measurement".
#: An explicitly passed ``None`` is malformed input, never a silent static fallback.
_UNSET = object()

#: A caption shorter than this cannot be a whole displayed effect sentence, so it is not
#: treated as complete evidence even when it happens to end in a terminal mark.
CAPTION_MIN_LENGTH = 16


# --------------------------------------------------------------------------------------
# Small validation helpers
# --------------------------------------------------------------------------------------

def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be a real number, got {value!r}')
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{label} must be finite, got {value!r}')
    return number


def _optional_number(value, label):
    return None if value is None else _number(value, label)


def _int_or_none(value, label):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'{label} must be an integer, got {value!r}')
    return value


def _nonempty_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a non-empty string')
    return value


def _text_or_empty(value, label):
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValueError(f'{label} must be a string, got {value!r}')
    return value


def _text_list(value, label):
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(f'{label} must be a list of strings')
    return [_nonempty_text(item, f'{label}[]') for item in value]


def _normalize(name):
    return ' '.join(_nonempty_text(name, 'name').split()).casefold()


def _json_safe(value):
    """Return ``value`` only if it is already pure JSON data with no NaN/Infinity."""
    text = json.dumps(value, allow_nan=False, sort_keys=True)
    return json.loads(text)


def read_weights(weights=None):
    """The static table actually in force, with every entry checked finite."""
    table = dict(DEFAULT_STATIC)
    if weights is not None:
        if not isinstance(weights, dict):
            raise ValueError('weights must be a mapping')
        for key, value in weights.items():
            if key not in DEFAULT_STATIC:
                raise ValueError(f'unknown static weight {key!r}')
            table[key] = _number(value, f'weights[{key!r}]')
    return table


def _base_result(score_key, version):
    return {
        'version': version,
        'score_key': list(score_key),
        'static_score': 0.0,
        'learned_score': 0.0,
        'score': 0.0,
        'reasons': [],
        'evidence': [],
        'refused': False,
        'refusal': None,
        'learned_applied': False,
        'learned_reason': None,
        'keywords': [],
        'known_keywords': [],
        'unknown_keywords': [],
        'model_trained': False,
    }


def _refuse(result, reason, evidence):
    result['refused'] = True
    result['refusal'] = reason
    result['reasons'] = [reason]
    result['static_score'] = 0.0
    result['learned_score'] = 0.0
    result['learned_applied'] = False
    result['score'] = 0.0
    result['evidence'] = list(evidence)
    return result


def _static_only(result, reasons, evidence):
    result['reasons'] = list(reasons)
    result['evidence'] = list(evidence)
    result['score'] = result['static_score']
    return result


# --------------------------------------------------------------------------------------
# Identity catalog (the only file access in this module, read-only)
# --------------------------------------------------------------------------------------

def load_identity_catalog(path):
    """Read and validate an identity catalog. Never writes, copies or caches."""
    target = Path(path)
    payload = json.loads(target.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'{target} is not a catalog object')
    catalog = validate_identity_catalog(payload)
    catalog['path'] = str(target)
    return catalog


def validate_identity_catalog(payload):
    """Validate the shipped identities shape and return a compact, immutable-ish view."""
    if not isinstance(payload, dict):
        raise ValueError('identity catalog must be an object')
    if payload.get('version') != 1:
        raise ValueError(f"unsupported identity catalog version {payload.get('version')!r}")
    rows = payload.get('identities')
    if not isinstance(rows, list) or not rows:
        raise ValueError('identity catalog needs a non-empty identities list')
    identities = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('identity catalog entries must be objects')
        try:
            identity_id = row['id']
            sinner = row['sinner']
            skills = row['skills']
        except KeyError as error:
            raise ValueError(f'identity entry missing {error.args[0]!r}') from None
        if isinstance(identity_id, bool) or not isinstance(identity_id, int):
            raise ValueError(f'identity id must be an integer, got {identity_id!r}')
        if isinstance(sinner, bool) or not isinstance(sinner, int) or not 1 <= sinner <= 13:
            raise ValueError(f'identity {identity_id}: sinner {sinner!r} outside 1..13')
        if not isinstance(skills, list) or not skills:
            raise ValueError(f'identity {identity_id}: a non-empty skill list is required')
        checked = []
        for skill in skills:
            if isinstance(skill, bool) or not isinstance(skill, int):
                raise ValueError(f'identity {identity_id}: skill ids must be integers')
            checked.append(skill)
        if len(set(checked)) != len(checked):
            raise ValueError(f'identity {identity_id}: duplicate skill ids')
        if identity_id in identities:
            raise ValueError(f'duplicate identity id {identity_id}')
        identities[identity_id] = {
            'id': identity_id,
            'sinner': sinner,
            'sinner_name': str(row.get('sinner_name') or ''),
            'name': str(row.get('name', '')),
            'title': str(row.get('title', '')),
            'name_en': str(row.get('title_en') or row.get('name_en') or ''),
            'buff_keywords': [str(item) for item in row.get('buff_keywords') or [] if str(item)],
            'skills': checked,
        }
    return {
        'version': 1,
        'identities': identities,
        'source': payload.get('source'),
        'commit': payload.get('commit'),
        'coverage': payload.get('coverage'),
        'note': payload.get('note'),
    }


# --------------------------------------------------------------------------------------
# Gift plan (the allow/block table preferences already own)
# --------------------------------------------------------------------------------------

def load_gift_plan(path, *, keyword=None, blocked=()):
    target = Path(path)
    payload = json.loads(target.read_text(encoding='utf-8'))
    plan = validate_gift_plan(payload, keyword=keyword, blocked=blocked)
    plan['path'] = str(target)
    return plan


def validate_gift_plan(payload, *, keyword=None, blocked=()):
    """Validate a gift plan and freeze the team's own wanted list.

    The shipped shape is the one ``gift_plan`` already owns: a ``default`` list plus a
    ``teams`` object keyed by team attribute. ``keyword`` selects the team's own list;
    an attribute with no list of its own falls back to ``default``. Nothing here decides
    which gift is better -- it only reports the plan's own verdict for a name.
    """
    if not isinstance(payload, dict):
        raise ValueError('gift plan must be an object')
    default = payload.get('default', [])
    teams = payload.get('teams', {})
    if default is None:
        default = []
    if teams is None:
        teams = {}
    if not isinstance(default, list) or not isinstance(teams, dict):
        raise ValueError('gift plan needs a "default" list and a "teams" object')
    for label, names in [('default', default)] + [
            (f'teams[{key!r}]', value) for key, value in teams.items()]:
        if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
            raise ValueError(f'gift plan {label} must be a list of gift names')
        seen = set()
        for name in names:
            token = _normalize(name)
            if token in seen:
                raise ValueError(f'gift plan {label} repeats gift name {name!r}')
            seen.add(token)

    key = (keyword or '').strip().lower()
    team_names = None
    for team_key, names in teams.items():
        if str(team_key).strip().lower() == key:
            team_names = list(names)
            break
    selected = team_names if key and team_names else list(default)

    wanted = {}
    order = []
    for name in selected:
        token = _normalize(name)
        if token in wanted:
            raise ValueError(f'gift plan repeats allowed name {name!r}')
        wanted[token] = str(name)
        order.append(str(name))
    refused = {}
    for name in blocked or []:
        if not isinstance(name, str):
            raise ValueError('gift plan blocked names must be strings')
        token = _normalize(name)
        if token in refused:
            raise ValueError(f'gift plan repeats blocked name {name!r}')
        if token in wanted:
            raise ValueError(f'gift plan allows and blocks {name!r} at once')
        refused[token] = str(name)
    return {
        'version': 1,
        'allowed': wanted,
        'blocked': refused,
        'order': order,
        'keyword': keyword,
        'team': {str(team_key): list(names) for team_key, names in teams.items()},
    }


def wanted(plan, name):
    """The plan's own verdict for one name: allowed, not allowed, or blocked."""
    if not isinstance(plan, dict):
        raise ValueError('gift plan must be an object')
    key = _normalize(name)
    if key in (plan.get('blocked') or {}):
        return 'blocked'
    return 'allowed' if key in (plan.get('allowed') or {}) else 'not_allowed'


# --------------------------------------------------------------------------------------
# Truncated captions are not evidence
# --------------------------------------------------------------------------------------

def caption_status(caption):
    """Audit a displayed caption. Truncated or unreadable text is never complete evidence.

    ``...``, a Unicode ellipsis, a wrapping ``..``, a missing terminal mark, a caption too
    short to be a whole effect sentence, or a value that is not text at all all read as
    incomplete, because a replacement effect that ends mid-sentence cannot be valued.
    """
    if not isinstance(caption, str):
        return False, 'caption_missing'
    text = caption.strip()
    if not text:
        return False, 'caption_missing'
    if any(marker in text for marker in _TRUNCATION_MARKERS):
        return False, 'caption_truncated'
    if text[-1] not in '.!?%\u3002\uff01\uff1f':
        return False, 'caption_not_terminated'
    if len(text) < CAPTION_MIN_LENGTH:
        return False, 'caption_too_short'
    return True, 'caption_complete'


def _nested_text(caption, texts):
    text = _text_or_empty(caption, 'caption').strip()
    candidates = [value.strip() for value in _text_list(texts, 'texts')]
    if not candidates:
        raise ValueError('at least one caption text is required')
    for candidate in candidates:
        if candidate == text or candidate in text or text in candidate:
            return True
    return False


# --------------------------------------------------------------------------------------
# Gift prediction: image evidence wins over the static gift base
# --------------------------------------------------------------------------------------

def gift_utility(name, *, plan, owned=False, keywords=None, keyword_weights=None,
                 image_score=_UNSET, image_source=None, trial_cost=0.0, artifact=None,
                 weights=None):
    """Score one predicted reward offer.

    ``image_score``/``image_source`` are what an independent image reader measured on the
    retained frame (the pre-image keywords on the card). When the caller supplies a finite
    image score, that measurement is the base and the shipped statics only break ties; with
    no image the static ``gift_base`` is a pre-image ordering value and the result says so.
    """
    table = read_weights(weights)
    result = _base_result(('gift', 'static_with_learning'), GIFT_SCORE_VERSION)
    title = _nonempty_text(name, 'name')
    key = _normalize(title)
    keyword_list = _text_list(keywords, 'keywords')
    evidence = [f'gift_plan={wanted(plan, title)}']

    if image_score is _UNSET:
        base = table['gift_base']
        evidence.append('image_source=static_base')
    else:
        base = _number(image_score, 'image_score')
        evidence.append(f'image_source={_nonempty_text(image_source, "image_source")}')

    trial = _number(trial_cost, 'trial_cost')
    if trial < 0:
        raise ValueError('trial_cost cannot be negative')
    if trial:
        base -= trial * table['trial_weight']
        evidence.append(f'trial_cost={trial}')

    if owned:
        base -= table['gift_owned']
        evidence.append('already_owned_penalty')
    preference = wanted(plan, title)
    if preference == 'blocked':
        return _refuse(result, 'gift_blocked', evidence)
    if preference == 'allowed':
        base += table['gift_preference']
        evidence.append('gift_preference_bonus')

    result['static_score'] = base
    reasons = [f'plan_status={preference}']
    if artifact:
        reasons.append(f'artifact={_nonempty_text(artifact, "artifact")}')

    learned = 0.0
    learned_applied = False
    learned_reason = 'not_scored_for_keywords'
    unknown_keywords = []
    if keyword_list:
        if keyword_weights is None:
            learned_reason = 'no_eligible_episodes'
        else:
            weight_map = _validate_weights_map(keyword_weights)
            matched = [weight_map[item] for item in keyword_list if item in weight_map]
            unknown_keywords = [item for item in keyword_list if item not in weight_map]
            if matched:
                learned = max(-1.0, min(1.0, max(matched)))
                learned_applied = learned != 0.0
                learned_reason = 'keyword_observations' if learned_applied else 'learned_zero'
            else:
                learned_reason = 'keyword_unobserved'
        if unknown_keywords:
            evidence.append('keyword_unobserved=' + ','.join(sorted(unknown_keywords)))
        if learned_applied:
            learned *= table['gift_learning_gain']
            reasons.append(f'learned_keywords={len(keyword_list)}')
    else:
        learned_reason = 'no_eligible_episodes' if keyword_weights is None else 'not_scored_for_keywords'

    result['learned_score'] = learned
    result['learned_applied'] = learned_applied
    result['learned_reason'] = learned_reason
    result['score'] = base + learned
    result['reasons'] = reasons
    result['evidence'] = evidence
    result['keywords'] = keyword_list
    result['unknown_keywords'] = unknown_keywords
    return result


# --------------------------------------------------------------------------------------
# Route: static kind weights, then a bounded learned re-rank over one floor's candidates
# --------------------------------------------------------------------------------------

def _route_weights(weights):
    """Split ``weights`` into the static table and an optional per-kind override table.

    A caller may pass either a flat static table, or the shipped route policy's own shape
    (``{'weights': {...}}`` from ``assets/resource/base/route-policy.json``) whose entries are
    named after the route kinds. In the shipped shape the kind entries are the kind table and
    only the remaining keys are static weights, so one file can seed both.
    """
    if weights is None:
        return None, None
    if not isinstance(weights, dict):
        raise ValueError('weights must be a mapping')
    nested = weights.get('weights')
    if isinstance(nested, dict):
        kinds = dict(nested)
        table = {key: value for key, value in weights.items() if key != 'weights'}
        return (table or None), kinds
    kinds = {key: value for key, value in weights.items()
             if key in ROUTE_KINDS and key != 'kinds'}
    nested_kinds = weights.get('kinds')
    if isinstance(nested_kinds, dict):
        kinds = dict(nested_kinds)
    table = {key: value for key, value in weights.items()
             if key not in ROUTE_KINDS and key != 'kinds'}
    return (table or None), (kinds or None)


def route_score(kind, *, floor=None, hp_ratio=None, candidates=None, weights=None,
                avoid_wounded=True, promote_fusion_shop=True, push_boss_on_last_floor=True):
    """Score one already-recognised node kind. This never proves a node identity."""
    static_table, kind_weights = _route_weights(weights)
    table = read_weights(static_table)
    result = _base_result(('route', 'node_kind'), ROUTE_SCORE_VERSION)
    if kind not in ROUTE_KINDS:
        return _refuse(result, 'route_kind_unknown', [f'kind={kind!r}'])
    base_weight = ROUTE_KIND_WEIGHTS[kind]
    if isinstance(kind_weights, dict):
        if kind not in kind_weights:
            return _refuse(result, 'route_kind_unknown', [f'kind={kind!r}'])
        base_weight = _number(kind_weights[kind], f'kinds[{kind!r}]')
    score = table['route_base'] + base_weight * table['route_weight']
    evidence = [f'kind={kind}', f'kind_weight={base_weight}']
    reasons = [f'kind={kind}']

    ratio = _optional_number(hp_ratio, 'hp_ratio')
    if ratio is not None:
        if not 0.0 <= ratio <= 1.0:
            raise ValueError('hp_ratio must be within 0..1')
        if avoid_wounded and ratio < 0.35:
            score -= 0.4
            reasons.append('avoid_wounded')
        evidence.append(f'hp_ratio={ratio}')

    floor_number = _int_or_none(floor, 'floor')
    if floor_number is not None:
        if not 1 <= floor_number <= 5:
            raise ValueError('floor must be within 1..5')
        if push_boss_on_last_floor and floor_number == 5 and kind == 'boss':
            score += 0.8
            reasons.append('push_boss_on_last_floor')
        evidence.append(f'floor={floor_number}')

    if candidates is not None and promote_fusion_shop and kind == 'shop' and candidates <= 1:
        score += 0.2
        reasons.append('promote_fusion_shop')
    result['static_score'] = score
    return _static_only(result, reasons, evidence)


def plan_route(candidates, *, floor=None, hp_ratio=None, weights=None,
               knowledge_base=None, avoid_wounded=True, promote_fusion_shop=True,
               push_boss_on_last_floor=True):
    """Order the candidates a reader already proved, best first, and report the split.

    Each candidate is ``{'name': str, 'kind': str, ...}``. Rows carry their static and learned
    components separately, ties keep the caller's input order (a stable sort), and the plan is
    deterministic and reproducible for one retained frame.
    """
    if not isinstance(candidates, (list, tuple)):
        raise ValueError('candidates must be a list')
    rows = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ValueError('route candidates must be objects')
        name = _nonempty_text(candidate.get('name'), f'candidates[{index}].name')
        kind = _nonempty_text(candidate.get('kind'), f'candidates[{index}].kind')
        scored = route_score(kind, floor=floor, hp_ratio=hp_ratio, weights=weights,
                             candidates=len(candidates), avoid_wounded=avoid_wounded,
                             promote_fusion_shop=promote_fusion_shop,
                             push_boss_on_last_floor=push_boss_on_last_floor)
        if scored['refused']:
            return {
                'version': ROUTE_SCORE_VERSION,
                'refused': True,
                'refusal': scored['refusal'],
                'rows': [],
                'chosen': None,
                'static_score': 0.0,
                'learned_score': 0.0,
                'score': 0.0,
                'learned_applied': False,
                'learned_reason': 'not_scored',
                'evidence': list(scored['evidence']),
                'model_trained': False,
            }
        rows.append({
            'name': name,
            'kind': kind,
            'static_score': scored['static_score'],
            'reasons': scored['reasons'],
            'evidence': scored['evidence'],
        })
    rows.sort(key=lambda row: -row['static_score'])
    learned_weights = (knowledge_base or {}).get('weights') if isinstance(knowledge_base, dict) else None
    applied = False
    for row in rows:
        weight = learned_weights.get(('route_kind', row['kind'])) if isinstance(learned_weights, dict) else None
        row['learned_score'] = 0.0 if weight is None else round(weight, 6)
        row['score'] = row['static_score'] + row['learned_score']
        if row['learned_score']:
            applied = True
            row['evidence'].append(f'route_kind_weight={row["learned_score"]:+.4f}')
    stable = sorted(rows, key=lambda row: -row['score'])
    chosen = stable[0] if stable else None
    return {
        'version': ROUTE_SCORE_VERSION,
        'refused': False,
        'refusal': None,
        'rows': stable,
        'chosen': chosen,
        'static_score': 0.0 if chosen is None else chosen['static_score'],
        'learned_score': 0.0 if chosen is None else chosen['learned_score'],
        'score': 0.0 if chosen is None else chosen['score'],
        'learned_applied': applied,
        'learned_reason': 'kind_observations' if applied else 'no_eligible_episodes',
        'evidence': [] if chosen is None else list(chosen['evidence']),
        'model_trained': False,
    }


# --------------------------------------------------------------------------------------
# Shop shelf
# --------------------------------------------------------------------------------------

def _validate_offers(offers):
    if not isinstance(offers, (list, tuple)):
        raise ValueError('offers must be a list')
    checked = []
    for index, offer in enumerate(offers):
        if not isinstance(offer, dict):
            raise ValueError('shop offers must be objects')
        name = _nonempty_text(offer.get('name'), f'offers[{index}].name')
        price = offer.get('price')
        if isinstance(price, bool) or not isinstance(price, int):
            raise ValueError(f'offers[{index}].price must be an integer, got {price!r}')
        if price < 0:
            raise ValueError(f'offers[{index}].price cannot be negative')
        checked.append({
            'name': name,
            'price': price,
            'keywords': _text_list(offer.get('keywords'), f'offers[{index}].keywords'),
            'owned': bool(offer.get('owned', False)),
            'curve_level': _int_or_none(offer.get('curve_level'), f'offers[{index}].curve_level'),
        })
    return checked


def shop_offer(offer, *, currency, plan=None, knowledge_base=None, owned_names=(),
               keywords=None, keyword_weights=None, weights=None, fusion_pending=False,
               health_required=False, expected=None):
    """Score one shelf offer against the run's own currency and the plan's verdict.

    The offer must be a mapping with an integer ``price``; an unpriced, non-integer or
    over-balance offer refuses rather than producing a number. Currency and price are the
    caller's measured facts, never inferred here. The static part is identity-only (plan
    verdict, fusion, health need); keyword influence lives entirely in the learned part, so no
    synergy is invented for a keyword that has no eligible observation.
    """
    table = read_weights(weights)
    if not isinstance(offer, dict):
        raise ValueError('offer must be an object')
    name = _nonempty_text(offer.get('name'), 'offer.name')
    result = _base_result(('shop', 'offer'), SHOP_SCORE_VERSION)
    balance = _int_or_none(currency, 'currency')
    if balance is None or balance < 0:
        return _refuse(result, 'shop_currency_unknown', [f'currency={currency!r}'])
    price = offer.get('price')
    if isinstance(price, bool) or not isinstance(price, int):
        return _refuse(result, 'shop_price_unknown', [f'price={price!r}'])
    if price < 0:
        return _refuse(result, 'shop_price_unknown', [f'price={price!r}'])
    if price > balance:
        return _refuse(result, 'shop_offer_unaffordable',
                       [f'price={price}', f'currency={balance}'])

    evidence = [f'price={price}', f'currency={balance}']
    if expected is not None:
        checked_expected = _nonempty_text(expected, 'expected')
        if _normalize(checked_expected) != _normalize(name):
            return _refuse(result, 'shop_offer_identity_mismatch',
                           evidence + [f'expected={checked_expected!r}', f'read={name!r}'])

    owned = {_normalize(item) for item in _text_list(list(owned_names), 'owned_names')}
    if offer.get('owned') or _normalize(name) in owned:
        return _refuse(result, 'shop_duplicate_owned', evidence + [f'owned={name!r}'])

    reason = 'plan_unspecified'
    if plan is not None:
        status = wanted(plan, name)
        if status == 'blocked':
            return _refuse(result, 'shop_offer_blocked', evidence + [f'plan={status}'])
        reason = f'plan={status}'
    evidence.append(reason)

    score = table['shop_offer_base']
    keywords_read = keywords if keywords is not None else offer.get('keywords', [])
    keyword_list = _text_list(keywords_read, 'keywords')
    derived = {} if keyword_weights is None else _validate_weights_map(keyword_weights)
    if fusion_pending:
        score += table['shop_fusion_bonus']
        evidence.append('fusion_pending_bonus')
    if health_required:
        score -= table['shop_health_risk']
        evidence.append('health_risk_penalty')

    learned = 0.0
    learned_applied = False
    learned_reason = 'not_scored_for_keywords'
    matched = []
    unknown_keywords = []
    if keyword_list:
        matched = [derived[item] for item in keyword_list if item in derived]
        unknown_keywords = [item for item in keyword_list if item not in derived]
        if not derived:
            learned_reason = 'no_eligible_episodes'
        elif matched:
            learned = max(-1.0, min(1.0, max(matched)))
            learned_applied = learned != 0.0
            learned_reason = 'keyword_observations' if learned_applied else 'learned_zero'
            if learned_applied:
                learned *= table['shop_learning_gain']
        else:
            learned_reason = 'keyword_unobserved'
    else:
        learned_reason = 'no_keywords'
    if unknown_keywords:
        evidence.append('keyword_unobserved=' + ','.join(sorted(set(unknown_keywords))))

    result['static_score'] = score
    result['learned_score'] = learned
    result['learned_applied'] = learned_applied
    result['learned_reason'] = learned_reason
    result['score'] = score + learned
    result['reasons'] = [reason]
    result['evidence'] = evidence
    result['keywords'] = keyword_list
    result['known_keywords'] = [item for item in keyword_list if item in derived]
    result['unknown_keywords'] = unknown_keywords
    return result


def shop_plan(*, offers, currency, plan=None, knowledge_base=None, owned_names=(),
              keyword_weights=None, weights=None, fusion_pending=False,
              health_required=False, refresh_limit=0, refreshes_used=0,
              refresh_cost=None, keyword_refresh_cost=None, refresh_allowed=True):
    """Buy order plus the refresh verdict for one shop page.

    ``buy_order`` lists only affordable, non-duplicate, non-blocked offers. ``priority`` keeps
    every offer with its refusal reason so an audit can see what was skipped and why. A
    refresh is recommended only when at least one offer was refused as
    ``shop_offer_unaffordable``, the refresh budget has room, and the refresh price is known
    and payable.
    """
    table = read_weights(weights)
    limits = _int_or_none(refresh_limit, 'refresh_limit')
    used = _int_or_none(refreshes_used, 'refreshes_used')
    if limits is None or limits < 0:
        raise ValueError('refresh_limit must be a non-negative integer')
    if used is None or used < 0:
        raise ValueError('refreshes_used must be a non-negative integer')
    balance = _int_or_none(currency, 'currency')
    if balance is None or balance < 0:
        raise ValueError('currency must be a non-negative integer')
    checked = _validate_offers(offers)

    priority = []
    for index, offer in enumerate(checked):
        row = shop_offer(offer, currency=balance, plan=plan,
                         knowledge_base=knowledge_base, owned_names=owned_names,
                         keyword_weights=keyword_weights, weights=weights,
                         fusion_pending=fusion_pending,
                         health_required=health_required)
        row['offer_index'] = index
        row['offer_name'] = offer['name']
        row['price'] = offer['price']
        priority.append(row)
    affordable = [row for row in priority if not row['refused']]
    affordable.sort(key=lambda row: (-row['score'], row['offer_index']))
    buy_order = [
        {'name': row['offer_name'], 'price': row['price'], 'score': row['score'],
         'static_score': row['static_score'], 'learned_score': row['learned_score'],
         'reasons': row['reasons']}
        for row in affordable
    ]

    unaffordable = any(row['refusal'] == 'shop_offer_unaffordable' for row in priority)
    reasons = []
    refresh = False
    if not refresh_allowed:
        reasons.append('refresh_disabled')
    elif not unaffordable:
        reasons.append('no_refused_offer')
    elif used >= limits:
        reasons.append('refresh_budget_exhausted')
    elif refresh_cost is None and keyword_refresh_cost is None:
        reasons.append('refresh_price_unknown')
    else:
        costs = [cost for cost in (_int_or_none(refresh_cost, 'refresh_cost'),
                                   _int_or_none(keyword_refresh_cost, 'keyword_refresh_cost'))
                 if cost is not None]
        if not costs or min(costs) > balance:
            reasons.append('refresh_unaffordable')
        else:
            refresh = True
            reasons.append('refresh_affordable')

    return {
        'version': SHOP_SCORE_VERSION,
        'currency': balance,
        'priority': priority,
        'buy_order': buy_order,
        'refresh': refresh,
        'refresh_reasons': reasons,
        'refresh_limit': limits,
        'refreshes_used': used,
        'model_trained': False,
        'weights_used': dict(table),
        'note': ('Static weights order offers a reader already priced; they are not the '
                 'game\'s numbers and prove no balance, identity or payout.'),
    }


# --------------------------------------------------------------------------------------
# Bounded skill replacement
# --------------------------------------------------------------------------------------

def skill_value(*, keywords=None, base_power=None, coin_power=None, caption=None,
                texts=None, weights=None, keyword_weights=None):
    """Value one skill's *read* facts. Unknown keywords contribute nothing and are reported.

    ``keywords`` are the buff keywords an independent reader mapped onto the skill, and
    ``keyword_weights`` is the learned map for those keywords (the same map the gift and shop
    scorers take). A keyword with no observed weight is never assigned a guessed synergy -- it
    is returned in ``unknown_keywords`` and contributes exactly nothing to ``value``.
    """
    table = read_weights(weights)
    keywords_list = _text_list(keywords, 'keywords')
    weight_map = {} if keyword_weights is None else _validate_weights_map(keyword_weights)
    complete, caption_reason = caption_status(caption)
    if caption and not complete:
        return {
            'version': SKILL_REPLACEMENT_VERSION,
            'value': None,
            'complete': False,
            'caption_reason': caption_reason,
            'known_keywords': [],
            'unknown_keywords': keywords_list,
            'evidence': [caption_reason],
            'model_trained': False,
        }
    if texts is not None and not _nested_text(caption, texts):
        return {
            'version': SKILL_REPLACEMENT_VERSION,
            'value': None,
            'complete': False,
            'caption_reason': 'caption_not_in_read_texts',
            'known_keywords': [],
            'unknown_keywords': keywords_list,
            'evidence': ['caption_not_in_read_texts'],
            'model_trained': False,
        }
    value = table['skill_base_weight']
    evidence = []
    matched = []
    unknown = []
    for item in keywords_list:
        if item in weight_map:
            contribution = table['skill_buff_weight'] * weight_map[item]
            value += contribution
            matched.append(item)
            evidence.append(f'{item}={contribution:+.4f}')
        else:
            unknown.append(item)
    power = _optional_number(base_power, 'base_power')
    if power is not None:
        value += power * 3.0
        evidence.append(f'base_power={power}')
    coins = _optional_number(coin_power, 'coin_power')
    if coins is not None:
        # Coin Power stays explicitly unsupported, exactly as docs/design.md already states.
        evidence.append(f'coin_power_unsupported={coins}')
    return {
        'version': SKILL_REPLACEMENT_VERSION,
        'value': value,
        'complete': complete,
        'caption_reason': caption_reason,
        'known_keywords': matched,
        'unknown_keywords': unknown,
        'evidence': evidence,
        'model_trained': False,
    }


def skill_replacement(*, sinner_name, identity_id, skill_id, caption, price, currency,
                      replaces, skill_captions=None, catalog, successor=None,
                      keywords=None, replaced_keywords=None, offers_per_visit=1,
                      replacements_used=0, max_replacements=1, weights=None,
                      keyword_weights=None):
    """Decide a shop skill replacement. Every required element must be readable.

    Required evidence, in order: a canonical sinner name, a skill id the loaded identity
    catalog already binds to that sinner, a complete caption read from the replacement page,
    an integer price inside the run's currency, the skill the replacement displaces, and the
    successor page that proves the replacement happened. ``offers_per_visit`` is 1 because a
    shop visit shows one replacement; a second request in the same visit refuses.

    ``keywords`` are the buff keywords the caller read for the replacement and
    ``replaced_keywords`` the ones read for the slot it displaces; each side is valued only
    from its own reading, so an unread side contributes no invented synergy.
    """
    table = read_weights(weights)
    result = _base_result(('skill_replacement', 'bounded'), SKILL_REPLACEMENT_VERSION)
    evidence = []
    if not isinstance(catalog, dict) or not isinstance(catalog.get('identities'), dict):
        return _refuse(result, 'skill_catalog_unavailable', ['catalog=invalid'])

    match = None
    for item in catalog['identities'].values():
        names = {_normalize(str(value)) for value in
                 (item.get('name'), item.get('sinner_name'), item.get('name_en')) if value}
        if sinner_name and _normalize(str(sinner_name)) in names:
            match = item
            break
        if identity_id is not None and item['id'] == identity_id:
            match = item
            break
    if match is None:
        return _refuse(result, 'skill_sinner_unknown', [f'sinner={sinner_name!r}',
                                                        f'identity={identity_id!r}'])
    localized = _normalize(str(match.get('name') or ''))
    requested = _normalize(str(sinner_name)) if sinner_name else ''
    foreign = {_normalize(str(value)) for value in
               (match.get('sinner_name'), match.get('name_en')) if value}
    if sinner_name and localized and requested != localized and requested not in foreign:
        return _refuse(result, 'skill_sinner_mismatch',
                       [f'sinner={sinner_name!r}', f'identity_name={match["name"]!r}'])
    if identity_id is not None and match['id'] != identity_id:
        return _refuse(result, 'skill_identity_mismatch',
                       [f'identity={identity_id}', f'catalog_identity={match["id"]}'])
    evidence.append(f"sinner_id={match['sinner']}")
    evidence.append(f"sinner_name={match.get('sinner_name') or match.get('name')!r}")
    evidence.append(f"identity_name={match.get('name')!r}")
    evidence.append(f'identity={match["id"]}')

    if isinstance(skill_id, bool) or not isinstance(skill_id, int):
        return _refuse(result, 'skill_id_unknown', evidence + [f'skill_id={skill_id!r}'])
    if skill_id not in match['skills']:
        return _refuse(result, 'skill_not_bound_to_identity',
                       evidence + [f'skill_id={skill_id}', f'identity_skills={match["skills"]}'])
    evidence.append(f'skill_id={skill_id}')

    if isinstance(replaces, bool) or not isinstance(replaces, int):
        return _refuse(result, 'skill_slot_unknown', evidence + [f'replaces={replaces!r}'])
    if replaces not in match['skills']:
        return _refuse(result, 'skill_slot_not_bound_to_identity',
                       evidence + [f'replaces={replaces}', f'identity_skills={match["skills"]}'])
    if replaces == skill_id:
        return _refuse(result, 'skill_slot_same_as_replacement', evidence)
    evidence.append(f'replaces={replaces}')

    cap_complete, caption_reason = caption_status(caption)
    if not cap_complete:
        result['caption_status'] = caption_reason
        return _refuse(result, f'skill_caption_{caption_reason.removeprefix("caption_")}',
                       evidence + [caption_reason])
    result['caption_status'] = caption_reason

    if successor is None:
        return _refuse(result, 'skill_successor_unproven', evidence + ['successor=None'])
    if not isinstance(successor, (dict, str)) or (
            isinstance(successor, str) and not successor.strip()):
        return _refuse(result, 'skill_successor_unproven', evidence + [f'successor={successor!r}'])
    if isinstance(successor, dict):
        successor_name = successor.get('name')
        if successor_name is not None and _normalize(str(successor_name)) not in (
                _normalize(str(skill_id)), 'earned skill', 'earned'):
            return _refuse(result, 'skill_successor_mismatch',
                           evidence + [f'successor={successor_name!r}'])
        if successor.get('verified') is False:
            return _refuse(result, 'skill_successor_unproven', evidence + ['verified=False'])
    evidence.append('successor=read')

    balance = _int_or_none(currency, 'currency')
    if balance is None or balance < 0:
        return _refuse(result, 'shop_currency_unknown', evidence + [f'currency={currency!r}'])
    if isinstance(price, bool) or not isinstance(price, int) or price < 0:
        return _refuse(result, 'skill_price_unknown', evidence + [f'price={price!r}'])
    if price > balance:
        return _refuse(result, 'skill_price_unaffordable',
                       evidence + [f'price={price}', f'currency={balance}'])
    evidence.append(f'price={price}')
    evidence.append(f'currency={balance}')

    offers = _int_or_none(offers_per_visit, 'offers_per_visit')
    used = _int_or_none(replacements_used, 'replacements_used')
    maximum = _int_or_none(max_replacements, 'max_replacements')
    if offers is None or offers <= 0:
        raise ValueError('offers_per_visit must be a positive integer')
    if used is None or used < 0:
        raise ValueError('replacements_used must be a non-negative integer')
    if maximum is None or maximum < 0:
        raise ValueError('max_replacements must be a non-negative integer')
    if replacements_used >= max_replacements:
        return _refuse(result, 'skill_replacement_budget_exhausted', evidence + [
            f'replacements_used={used}', f'max_replacements={maximum}'])

    old_value = None
    # The replacement is valued on the keywords the caller read for it (or none). The displaced
    # side is valued on its own separately read keywords, never silently assumed to carry the
    # replacement's: assuming that would fabricate the old side's synergy and cancel the delta.
    new_keywords = _text_list(keywords, 'keywords')
    displaced_keywords = _text_list(replaced_keywords, 'replaced_keywords')
    if skill_captions is not None:
        if not isinstance(skill_captions, dict):
            raise ValueError('skill_captions must be a mapping of skill id -> caption')
        if replaces in skill_captions:
            displaced = skill_captions[replaces]
            displaced_complete, reason = caption_status(displaced)
            if not displaced_complete:
                return _refuse(result, 'skill_replaced_caption_incomplete',
                               evidence + [f'replaces={replaces}', reason])
            # The displaced slot is valued on the same keyword basis as the replacement, so a
            # delta of zero really means "no gain", not "the old side was read more thinly".
            old_value = skill_value(caption=displaced, keywords=displaced_keywords,
                                    weights=weights, keyword_weights=keyword_weights)['value']
            evidence.append(f'replaced_value={old_value}')
            evidence.append(f'replaced_keywords={list(displaced_keywords)}')
        else:
            return _refuse(result, 'skill_replaced_caption_missing',
                           evidence + [f'replaces={replaces}'])

    value = skill_value(keywords=new_keywords, caption=caption, weights=weights,
                        keyword_weights=keyword_weights)
    if value['value'] is None:
        return _refuse(result, f'skill_caption_{value["caption_reason"].removeprefix("caption_")}',
                       evidence + [value['caption_reason']])
    delta = float(value['value']) if old_value is None else float(value['value']) - float(old_value)
    if old_value is not None and delta <= 0:
        return _refuse(result, 'skill_replacement_no_gain',
                       evidence + [f'new_value={value["value"]}', f'delta={delta:+.4f}'])

    result['static_score'] = delta
    result['learned_score'] = 0.0
    result['learned_applied'] = False
    result['learned_reason'] = 'not_scored_for_keywords'
    result['score'] = delta
    result['reasons'] = ['skill_replacement_bounded', f'delta={delta:+.4f}']
    result['evidence'] = evidence + list(value['evidence'])
    result['cache_key'] = ['skill_replacement', match['id'], skill_id, replaces, price]
    result['slot'] = match['skills'].index(replaces)
    result['identity_id'] = match['id']
    result['sinner'] = match['name']
    result['skill_id'] = skill_id
    result['replaces'] = replaces
    result['price'] = price
    result['currency'] = balance
    result['caption_status'] = caption_reason
    result['unknown_keywords'] = list(value['unknown_keywords'])
    result['known_keywords'] = list(value['known_keywords'])
    return result


# --------------------------------------------------------------------------------------
# Learned layer inputs: only a verified episode outcome may move these
# --------------------------------------------------------------------------------------

def _validate_weights_map(weights):
    if not isinstance(weights, dict):
        raise ValueError('keyword weights must be a mapping of keyword -> number')
    checked = {}
    for key, value in weights.items():
        checked[_nonempty_text(key, 'keyword')] = _number(value, f'keyword_weights[{key!r}]')
    return checked


def new_knowledge_base(weights=None):
    return {
        'version': POLICY_VERSION,
        'weights': {},
        'knowledge': {
            'episodes': 0,
            'learning_eligible_episodes': 0,
            'censored_episodes': 0,
            'events': {},
            'shop': {'wins': 0, 'points': 0.0, 'spent': 0, 'purchase_events': 0,
                     'skill_replacements': []},
            'route': {'events': 0, 'points': 0.0},
            'gift': {'picks': 0, 'points': 0.0},
        },
        'sources': [],
        'model_trained': False,
        'limitation': ('Bounded tally of verified episode outcomes; not a trained model and '
                       'not a claim that any game run was completed for training.'),
    }


def _event(state, feature):
    return state['knowledge']['events'].setdefault(
        feature, {'events': 0, 'points': 0.0, 'positive': 0, 'max_points': 0.0})


def _fold_events(state, features, points, positive):
    for feature in features:
        if feature is None:
            continue
        row = _event(state, tuple(feature))
        row['events'] += 1
        row['points'] += float(points)
        row['positive'] += 1 if positive else 0
        if float(points) > row['max_points']:
            row['max_points'] = float(points)


def update_outcome(state, outcome):
    """Fold one verified episode outcome into the knowledge base and re-derive weights.

    Inputs are the assessment's own facts plus what the run actually did. The update refuses
    an outcome whose completion numbers disagree with the floors it claims, and an outcome
    that is censored (or explicitly ineligible) never reaches the learned weights -- it is
    counted as evidence, not as learning.
    """
    if not isinstance(state, dict):
        raise ValueError('knowledge base state must be an object')
    knowledge = state.get('knowledge')
    if not isinstance(knowledge, dict):
        raise ValueError('knowledge base state is missing its knowledge block')
    if not isinstance(outcome, dict):
        raise ValueError('outcome must be an object')
    episode = _nonempty_text(outcome.get('episode'), 'outcome.episode')
    scope = _nonempty_text(outcome.get('scope'), 'outcome.scope')
    date = _nonempty_text(outcome.get('date'), 'outcome.date')
    floors = outcome.get('floors')
    if isinstance(floors, bool) or not isinstance(floors, int) or not 0 <= floors <= 5:
        raise ValueError('outcome.floors must be an integer within 0..5')
    victory = bool(outcome.get('victory'))
    reward = bool(outcome.get('reward'))
    progress = _optional_number(outcome.get('progress'), 'outcome.progress')
    expected_progress = 20 * floors + 10 * int(victory) + 10 * int(reward)
    if progress is not None and int(progress) != expected_progress:
        raise ValueError(f'outcome.progress {progress!r} disagrees with '
                         f'floors/victory/reward ({expected_progress})')
    if victory and not outcome.get('completion_verified'):
        raise ValueError('a claimed victory needs completion_verified')
    if reward and not outcome.get('reward_verified'):
        raise ValueError('a claimed reward needs reward_verified')
    eligible = bool(outcome.get('strategy_training_eligible'))
    censored = bool(outcome.get('censored', not eligible))
    learning_eligible = eligible and not censored

    picked = _text_list(outcome.get('gift_picks'), 'outcome.gift_picks')
    keywords = _text_list(outcome.get('gift_keywords'), 'outcome.gift_keywords')
    route_kinds = _text_list(outcome.get('route_kinds'), 'outcome.route_kinds')
    for kind in route_kinds:
        if kind not in ROUTE_KINDS:
            raise ValueError(f'outcome.route_kinds contains unknown kind {kind!r}')
    purchases = outcome.get('shop_purchases') or []
    if not isinstance(purchases, (list, tuple)):
        raise ValueError('outcome.shop_purchases must be a list')
    replacements = outcome.get('skill_replacements') or []
    if not isinstance(replacements, (list, tuple)):
        raise ValueError('outcome.skill_replacements must be a list')

    for index, item in enumerate(purchases):
        if not isinstance(item, dict):
            raise ValueError('shop purchases must be objects')
        _nonempty_text(item.get('name'), f'shop_purchases[{index}].name')
        price = item.get('price')
        if isinstance(price, bool) or not isinstance(price, int) or price < 0:
            raise ValueError(f'shop_purchases[{index}].price must be a non-negative integer')
    for index, item in enumerate(replacements):
        if not isinstance(item, dict):
            raise ValueError('skill replacements must be objects')
        for field in ('sinner', 'successor'):
            _nonempty_text(item.get(field), f'skill_replacements[{index}].{field}')
        for field in ('skill_id', 'replaces', 'price', 'delta'):
            if field not in item:
                raise ValueError(f'skill_replacements[{index}] needs {field}')

    updated = copy.deepcopy(state)
    updated['version'] = state.get('version', POLICY_VERSION)
    row = updated['knowledge']
    row['episodes'] += 1
    row['censored_episodes'] += 1 if censored else 0
    points = expected_progress
    if learning_eligible:
        row['learning_eligible_episodes'] += 1

    gift_points = float(points) if learning_eligible else 0.0
    if picked or keywords:
        row['gift']['picks'] += len(picked) or len(keywords)
        row['gift']['points'] += gift_points
    if learning_eligible and (picked or keywords):
        features = [('gift_keyword', item) for item in keywords]
        _fold_events(updated, features, points, reward)
    if learning_eligible and route_kinds:
        row['route']['events'] += len(route_kinds)
        row['route']['points'] += points
        _fold_events(updated, [('route_kind', item) for item in route_kinds], points, reward)
    if learning_eligible and purchases:
        row['shop']['purchase_events'] += len(purchases)
        row['shop']['wins'] += 1
        row['shop']['points'] += points
        for item in purchases:
            _fold_events(updated, [('gift_keyword', keyword)
                                   for keyword in _text_list(item.get('keywords'),
                                                             'shop purchase keywords')],
                         points, reward)
    if learning_eligible and replacements:
        for item in replacements:
            row['shop']['skill_replacements'].append({
                'sinner': item['sinner'],
                'skill_id': item['skill_id'],
                'replaces': item['replaces'],
                'price': item['price'],
                'delta': float(item['delta']),
            })

    derived = {}
    knowledge_state = updated['knowledge']
    for (space, name), stats in sorted(knowledge_state['events'].items()):
        if space not in ('gift_keyword', 'route_kind'):
            continue
        if stats['events'] < LEARNED_MIN_EVENTS:
            continue
        mean_points = stats['points'] / stats['events']
        prior_mean = max(1.0, stats['max_points'])
        rate = (mean_points - prior_mean / 2.0) / (prior_mean / 2.0)
        rate = max(-LEARNED_RATE_CAP, min(LEARNED_RATE_CAP, rate))
        adjustment = rate * LEARNED_GAIN
        adjustment = max(-LEARNED_ADJUST_CAP, min(LEARNED_ADJUST_CAP, adjustment))
        derived[(space, name)] = round(adjustment, 6)
    updated['weights'] = derived
    updated['sources'] = sorted(set(state.get('sources', [])) | {f'{episode}@{scope}@{date}'})
    updated['model_trained'] = False
    updated['last_episode'] = episode
    return updated


def knowledge_base_for(outcomes, state=None):
    """Build a knowledge base from an episode outcome list, in the order given."""
    current = new_knowledge_base() if state is None else state
    for outcome in outcomes:
        current = update_outcome(current, outcome)
    return current


# --------------------------------------------------------------------------------------
# Shared learned term
# --------------------------------------------------------------------------------------

def _learned_adjust(weights, feature, base_static=1.0):
    """Return ``(adjustment, reason, key)``. No observations means no learned term at all."""
    if feature is None or not weights:
        return 0.0, 'no_eligible_episodes', None
    key = (feature[0], feature[1]) if isinstance(feature, tuple) else feature
    if key not in weights:
        return 0.0, 'feature_unobserved', None
    value = _number(weights[key], f'weights[{key!r}]')
    if value == 0.0:
        return 0.0, 'learned_zero', key
    scale = abs(_number(base_static, 'static_score'))
    if scale <= 0.0:
        return 0.0, 'static_scale_zero', key
    return value * scale * 0.05, 'observed', key


def strategy_score(*, kind, feature, static_score, knowledge_base=None, weights=None):
    """Combine one decision's static score with the bounded learned adjustment.

    ``kind`` is one of ``DECISION_KINDS``; ``feature`` is ``(space, name)`` such as
    ``('gift_keyword', 'Bleed')``. The learned term is zero whenever the knowledge base holds
    no eligible observation of that feature, and the result says which case it was. The whole
    adjustment stays inside ``LEARNED_ADJUST_CAP`` times the static magnitude, so it can never
    run away in either direction.
    """
    if kind not in DECISION_KINDS:
        raise ValueError(f'unknown decision kind {kind!r}')
    read_weights(weights)
    static = _number(static_score, 'static_score')
    base = knowledge_base if isinstance(knowledge_base, dict) else {}
    table_map = base.get('weights') if isinstance(base.get('weights'), dict) else {}
    adjustment, reason, matched = _learned_adjust(table_map, feature, static)
    if reason == 'observed':
        adjustment = max(-LEARNED_ADJUST_CAP * abs(static),
                         min(LEARNED_ADJUST_CAP * abs(static), adjustment))
    total = static + adjustment
    result = _base_result((kind, 'static_with_learning'), POLICY_VERSION)
    result['static_score'] = static
    result['learned_score'] = adjustment
    result['score'] = total
    result['learned_applied'] = adjustment != 0.0
    result['learned_reason'] = reason
    result['feature'] = list(feature) if isinstance(feature, (tuple, list)) else feature
    result['reasons'] = ['static_heuristic' if adjustment == 0.0 else 'static_plus_learned']
    result['evidence'] = [f'static={static}', f'learned={adjustment}',
                          f'learned_reason={reason}']
    if matched is not None:
        result['evidence'].append(f'learned_source={matched[0]}:{matched[1]}')
    return result


def policy_summary(knowledge_base=None):
    """One JSON-safe summary for a tool, a UI card or a handoff record."""
    base = knowledge_base if isinstance(knowledge_base, dict) else {}
    knowledge = base.get('knowledge') if isinstance(base.get('knowledge'), dict) else {}
    weights = base.get('weights') if isinstance(base.get('weights'), dict) else {}
    return _json_safe({
        'version': POLICY_VERSION,
        'decision_kinds': list(DECISION_KINDS),
        'route_kinds': list(ROUTE_KINDS),
        'episodes': int(knowledge.get('episodes', 0)),
        'learning_eligible_episodes': int(knowledge.get('learning_eligible_episodes', 0)),
        'censored_episodes': int(knowledge.get('censored_episodes', 0)),
        'features': sorted(f'{space}:{name}' for (space, name) in weights),
        'weights': {f'{space}:{name}': value for (space, name), value in sorted(weights.items())},
        'model_trained': False,
        'static_only_until': 'strategy_training_eligible outcomes',
        'source': 'wiki-public facts + retained in-run evidence only',
        'not_claimed': ['model trained', 'game completed for training', 'optimal strategy',
                        'payout', 'node identity'],
    })


__all__ = [
    'POLICY_VERSION',
    'DECISION_KINDS',
    'ROUTE_KINDS',
    'DEFAULT_STATIC',
    'ROUTE_KIND_WEIGHTS',
    'LEARNED_ADJUST_CAP',
    'load_identity_catalog',
    'validate_identity_catalog',
    'load_gift_plan',
    'validate_gift_plan',
    'wanted',
    'caption_status',
    'read_weights',
    'gift_utility',
    'route_score',
    'plan_route',
    'shop_offer',
    'shop_plan',
    'skill_value',
    'skill_replacement',
    'new_knowledge_base',
    'update_outcome',
    'knowledge_base_for',
    'strategy_score',
    'policy_summary',
]
