"""Order the candidate nodes of one Mirror Dungeon floor (offline, pure).

`map_vision` proves *that* a node is a candidate on this floor and refuses when
the evidence is thin.  This module only orders candidates whose **kind** is
already known, using an editable policy table
(`assets/resource/base/route-policy.json`) instead of a hard-coded priority.

`floor-graph.json` is *not* this file: the plan reserves that name for the
per-floor numeric model that map perception writes at runtime (nodes, links,
current row/column, pack name, floor number); this policy is what scores the
candidates that model hands over.  Nothing here is read out of pixels:

* a candidate whose kind is not in the policy is ignored,
* if no candidate survives that filter the plan is a **refusal**, never a guess,
* the same input always yields the same output (ties break on input order).

The weights in the shipped policy are a starting preference, not a claim about
the game's internal numbers: they are meant to be edited and re-tested offline.
"""

from __future__ import annotations

import json
from pathlib import Path

KINDS = (
    'boss',
    'elite',
    'focused',
    'abnormality',
    'event',
    'regular',
    'shop',
    'empty',
)
POLICY_VERSION = 1
MODIFIERS = ('avoid_wounded', 'promote_fusion_shop', 'push_boss_on_last_floor')


class PolicyError(ValueError):
    """The policy file is not a usable floor-graph."""


def load_policy(path: str | Path) -> dict:
    """Load and validate a floor-graph policy table."""
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise PolicyError('floor-graph must be an object')
    if raw.get('version') != POLICY_VERSION:
        raise PolicyError('floor-graph version must be %d' % POLICY_VERSION)
    weights = raw.get('weights')
    if not isinstance(weights, dict) or not weights:
        raise PolicyError('floor-graph needs a non-empty weights object')
    for kind, weight in weights.items():
        if kind not in KINDS:
            raise PolicyError('unknown node kind %r in weights' % kind)
        if not isinstance(weight, (int, float)) or isinstance(weight, bool):
            raise PolicyError('weight for %r must be a number' % kind)
    modifiers = raw.get('modifiers', {})
    if not isinstance(modifiers, dict):
        raise PolicyError('floor-graph modifiers must be an object')
    for name, value in modifiers.items():
        if name not in MODIFIERS:
            raise PolicyError('unknown modifier %r' % name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PolicyError('modifier %r must be a number' % name)
    return {
        'version': POLICY_VERSION,
        'weights': {kind: float(weight) for kind, weight in weights.items()},
        'modifiers': {name: float(value) for name, value in modifiers.items()},
        'note': raw.get('note'),
    }


def score_node(kind: str, *, policy: dict, context: dict | None = None) -> dict | None:
    """Score one node kind; `None` when the policy does not score that kind."""
    weight = policy['weights'].get(kind)
    if weight is None:
        return None
    score = weight
    reasons = ['base_weight_%s' % kind]
    context = context or {}
    modifiers = policy['modifiers']

    wounded = context.get('wounded_ratio')
    if kind in ('elite', 'boss') and wounded is not None:
        penalty = modifiers.get('avoid_wounded', 0.0) * float(wounded)
        if penalty:
            score -= penalty
            reasons.append('wounded_penalty_%.3f' % penalty)

    if kind == 'shop' and context.get('fusion_pending'):
        bonus = modifiers.get('promote_fusion_shop', 0.0)
        if bonus:
            score += bonus
            reasons.append('fusion_shop_bonus_%.3f' % bonus)

    floor = context.get('floor')
    if kind == 'boss' and floor is not None and context.get('last_floor'):
        bonus = modifiers.get('push_boss_on_last_floor', 0.0)
        if bonus:
            score += bonus
            reasons.append('last_floor_boss_bonus_%.3f' % bonus)

    return {'kind': kind, 'score': round(score, 6), 'reasons': reasons}


def plan_route(candidates, *, policy: dict, context: dict | None = None) -> dict:
    """Pick the best candidate node, or refuse with a reason.

    `candidates` is a sequence of mappings with an `id` and a `kind`; an
    optional `box` is carried through to the answer so a caller can click it.
    A candidate whose kind the policy does not score is skipped; when no
    candidate survives, the plan refuses (`route_kind_unknown`).
    """
    candidates = list(candidates)
    if not candidates:
        return dict(target=None, box=None, kind=None, score=None,
                    reasons=[], ranked=[], refused='route_candidates_empty')

    ranked = []
    for index, candidate in enumerate(candidates):
        kind = candidate.get('kind')
        scored = score_node(kind, policy=policy, context=context) if kind else None
        if scored is None:
            continue
        ranked.append(dict(scored, id=candidate.get('id'), box=candidate.get('box'),
                           index=index))

    if not ranked:
        return dict(target=None, box=None, kind=None, score=None,
                    reasons=[], ranked=[], refused='route_kind_unknown')

    ranked.sort(key=lambda entry: (-entry['score'], entry['index']))
    best = ranked[0]
    return dict(target=best['id'], box=best['box'], kind=best['kind'],
                score=best['score'], reasons=list(best['reasons']),
                ranked=ranked, refused=None)
