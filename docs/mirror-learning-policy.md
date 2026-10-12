# Mirror learning policy

`src/maalimbus/mirror_learning_policy.py` is a **pure, offline policy module**. It turns facts
that an independent reader already proved into auditable numbers: how much a predicted floor-gift
slot is worth, which already-identified map node to prefer, which shop offer to buy, and whether a
bounded skill replacement is proven enough to allow. It also folds complete, verified episode
outcomes into a bounded tally that can nudge those numbers.

It touches nothing else: no screenshots, no input, no controller, no game process, no network, no
files of its own, and no training. Every function is deterministic and side-effect free, and every
result is plain JSON data.

## What this module does not claim

These are limits, not disclaimers. A caller that violates them is misusing the policy.

- **No model is trained.** `model_trained` is `False` on every result, and the learned layer is a
  bounded tally of verified outcomes, not a fitted model. `new_knowledge_base()` says so in its
  `limitation` field.
- **No game run is claimed.** The module never asserts that a run was played, a screen was seen, or
  a reward was received. Only the caller's verified completion evidence can say that.
- **Static weights are heuristics, not game formulas** (same posture as `docs/design.md`). They
  order candidates; they are not a claim about the game's internal numbers and not a claim of a
  universally optimal choice.
- **No node identity, offer identity, or image meaning is invented.** Node kinds, gift names, and
  skill ids arrive already read. This module ranks them; it never decides what they are.
- **An unread side contributes nothing.** An unknown keyword, an unobserved feature, a missing
  caption or a missing price contributes exactly zero, and the result names that case instead of
  guessing.
- **No private data.** The module reads no account state, no budget ledger, no configuration and no
  screenshot. Paths are only ever what the caller passes to `load_identity_catalog` /
  `load_gift_plan`.

## The static / learned split

Every scoring result carries the split explicitly:

| field | meaning |
| --- | --- |
| `static_score` | the shipped or caller-supplied deterministic heuristic |
| `learned_score` | the bounded adjustment derived from eligible verified outcomes |
| `score` | `static_score + learned_score` |
| `learned_applied` | whether a nonzero learned term was used |
| `learned_reason` | why: `no_eligible_episodes`, `feature_unobserved`, `learned_zero`, `observed`, `static_scale_zero`, `not_scored_for_keywords`, `kind_observations` |
| `evidence` | the literal inputs and arithmetic that produced the numbers |
| `model_trained` | always `False` |

`score == static_score + learned_score` whenever the result is not refused; a refusal has no score
at all. The learned term is bounded twice: the per-event rate is clamped to
`LEARNED_RATE_CAP = 1.0` by `LEARNED_GAIN = 1.0`, and the whole adjustment is clamped to
`LEARNED_ADJUST_CAP = 2.0`. In `strategy_score`, the adjustment is additionally capped at
`LEARNED_ADJUST_CAP` times the static magnitude, so it can never outrun the static term.

**With no eligible episodes the learned term is exactly `0.0`** and the result says
`no_eligible_episodes`. Nothing in this module fabricates a learned contribution to look useful.

## Inputs it reuses (and does not duplicate)

- `load_identity_catalog(path)` / `validate_identity_catalog(payload)` — the repo's existing
  `assets/resource/base/identity-catalog.json` shape (`version`, `identities`). Sinner ids are
  canonical (`1..13`), an identity id is bound to exactly one sinner, and a skill id must already
  be bound to that identity before any replacement may be scored.
- `load_gift_plan(path)` / `validate_gift_plan(payload)` / `wanted(plan, name)` — the existing
  `gift-plan.json` shape with a `default` list and a `teams` object. A blocked name always wins, a
  repeated name inside one list is refused as malformed input, and the result is one of
  `allowed`, `blocked`, `not_allowed`.
- `route_score` / `plan_route` mirror `src/maalimbus/route_plan.py`: the same
  `ROUTE_KINDS`/`POLICY_VERSION` vocabulary and the same shipped `route-policy.json` weights
  (`boss 3.0, elite 2.4, focused 2.2, abnormality 1.8, event 1.6, regular 1.4, shop 1.2, empty 0.2`),
  importable as the fallback static table. **`route_plan.py` remains the module that decides a
  click**; this module only scores and orders already-identified candidates.

## Gift utility

`gift_utility(name, *, plan, owned=False, keywords=None, keyword_weights=None, image_score=..., image_source=None, trial_cost=0.0, artifact=None, weights=None)`

- The gift must resolve through the plan first; a blocked gift is refused.
- When the caller supplies a finite `image_score` (what an independent image reader measured on the
  retained frame), that measurement is the base and the shipped static only breaks ties. With no
  image, the static `gift_base` is a pre-image ordering value and `evidence` says
  `image_source=static_base`.
- An explicitly passed `image_score=None` is **malformed input** (`ValueError`), not a silent
  static fallback; omitting the argument entirely is the static case.
- Owned gifts are discounted (`gift_owned`), plan-preferred names are lifted (`gift_preference`),
  and a nonzero `trial_cost` is applied with `trial_weight` and named in `evidence`.
- Learned: the maximum observed keyword weight for the gift's keywords, clamped to `+/-1`, scaled
  by `gift_learning_gain`. Unknown keywords are returned in `unknown_keywords` and contribute
  nothing.

## Route planning

`route_score(kind, *, floor=None, hp_ratio=None, candidates=None, weights=None, avoid_wounded=True, promote_fusion_shop=True, push_boss_on_last_floor=True)`
`plan_route(candidates, *, floor=None, hp_ratio=None, weights=None, knowledge_base=None, ...)`

- An unknown kind is refused as `route_kind_unknown` — this module never maps an unidentified node.
- The three modifiers are applied only when their precondition is actually present (wounded state,
  a pending fusion shop, the last floor) and each is named in `evidence`.
- `weights` accepts the shipped `route-policy.json` shape directly, so the static table and the
  per-kind table can come from one file.
- `plan_route` keeps the caller's input order on ties, reports every scored candidate in `rows`,
  and repeats the chosen row's `static_score`/`learned_score`/`score` at the top level.
- **Routing stays a refusal until identity exists** (`docs/design.md`): a next node may be planned
  only when the page is an identified map, one current-position marker is proven, and exactly one
  unvisited candidate remains. This module scores a candidate list; it does not establish that.

## Shop shelf

`shop_offer(offer, *, currency, plan=None, knowledge_base=None, owned_names=(), keywords=None, keyword_weights=None, weights=None, fusion_pending=False, health_required=False, expected=None)`
`shop_plan(*, offers, currency, ...)`

- An offer with no readable price is not silently cheap: it is refused as `offer_price_unknown`
  so a caller can still refuse it by name.
- Currency is required and must cover the price; an unaffordable offer is refused, and the plan
  buys the best affordable offer rather than the best offer.
- Unidentified offers are refused; owned duplicates are penalised (`shop_duplicate`), and a pending
  fusion or a required health purchase is named in `evidence` rather than folded into the base.
- `shop_plan` plans a **bounded** plain refresh: it fires only when the refresh is affordable,
  inside `refresh_limit`, not already `refreshes_used`, and `refresh_allowed`. Each condition is
  reported in `refresh_reasons`. The keyword refresh price is considered when supplied.

## Bounded skill replacement

`skill_replacement(*, sinner_name, identity_id, skill_id, caption, price, currency, replaces, skill_captions=None, catalog, successor=None, keywords=None, replaced_keywords=None, offers_per_visit=1, replacements_used=0, max_replacements=1, weights=None, keyword_weights=None)`

This is the policy the pending receipt blocker (`PROJECT.md`) needs: it is only ever allowed to
answer from evidence, and anything it cannot read is a **STOP**, never a default.

The checks run in this order, and the first failure refuses with its own code:

| order | condition | refusal code |
| --- | --- | --- |
| 1 | catalog absent or not the expected shape | `skill_catalog_unavailable` |
| 2 | no catalog identity matches the sinner or identity id | `skill_sinner_unknown` |
| 3 | the name given contradicts the matched identity | `skill_sinner_mismatch` |
| 4 | the name matches one identity, the id another | `skill_identity_mismatch` |
| 5 | `skill_id` is not an integer | `skill_id_unknown` |
| 6 | `skill_id` is not bound to that identity | `skill_not_bound_to_identity` |
| 7 | `replaces` is not an integer | `skill_slot_unknown` |
| 8 | `replaces` is not bound to that identity | `skill_slot_not_bound_to_identity` |
| 9 | `replaces == skill_id` | `skill_slot_same_as_replacement` |
| 10 | caption missing / truncated / unterminated / too short | `skill_caption_missing`, `skill_caption_truncated`, `skill_caption_not_terminated`, `skill_caption_too_short` |
| 11 | no successor evidence | `skill_successor_unproven` |
| 12 | successor names something other than the skill | `skill_successor_mismatch` |
| 13 | currency missing | `shop_currency_unknown` |
| 14 | price missing or not an integer | `skill_price_unknown` |
| 15 | price exceeds currency | `skill_price_unaffordable` |
| 16 | this visit's replacements are used up | `skill_replacement_budget_exhausted` |
| 17 | the displaced skill's own caption is unreadable | `skill_replaced_caption_incomplete` |
| 18 | the displaced skill's caption was not supplied | `skill_replaced_caption_missing` |
| 19 | the replacement is worth no more than the slot | `skill_replacement_no_gain` |

`caption_status(caption)` is the shared audit: `caption_missing`, `caption_truncated` (any of
`...`, `…`, `⋯`, `..`), `caption_not_terminated` (must end in `.`, `!`, `?`, `%`, `。`, `！`, `？`),
`caption_too_short` (under `CAPTION_MIN_LENGTH = 16` characters), else `caption_complete`. A
replacement effect that ends mid-sentence cannot be valued, so it is not complete evidence.

`skill_value(*, keywords=None, base_power=None, coin_power=None, caption=None, texts=None, weights=None, keyword_weights=None)`
values one skill from read facts only: base `skill_base_weight`, plus `skill_buff_weight` times each
*observed* keyword weight. **A keyword with no observation contributes exactly zero** and is
returned in `unknown_keywords`; `coin_power` is explicitly unsupported and reported as such. When
`texts` is supplied, the caption must appear in the independently read text or the value is `None`
with `caption_not_in_read_texts`. Each side of a swap is valued from **its own** reading
(`keywords` / `replaced_keywords`), so an unread side cannot fabricate a delta.

### The offline reading of the known blocker

`PROJECT.md` records that the old global trial/cost screen wrongly rejected the gift descriptions
`Shop Skill Replacement Cost` and `Max HP`, which kept a receipt pending. This module keeps those
two concerns apart by construction:

- `Shop Skill Replacement Cost` is a **cost/effect description**. It travels as `caption` text and is
  audited by `caption_status`; it is never treated as proof of the replacement itself, and never as
  a trial or payment.
- A **trial or payment** is a separate, explicit act: a `trial_cost` passed to `gift_utility`, or the
  `price` plus `currency` plus `successor` evidence passed to `skill_replacement`. Neither is
  inferred from any description string.
- `Max HP` therefore contributes to neither side unless a caller supplies it as a value with its own
  evidence; no wording match inside a description can move a score.

The consequence for the pending receipt: this module can score a replacement only once the caption,
price, currency, displaced slot and successor are all read. Until then it returns a refusal code and
a `STOP`, and it never acknowledges, selects, or clears an unknown pending transaction.

## Episode results and the learned tally

`update_outcome(state, outcome)` folds **one verified episode** into `new_knowledge_base()` state and
re-derives `weights`. An outcome's facts are the assessment's own:

```json
{
  "episode": "20261012-team7-hard", "scope": "scope4734", "date": "2026-10-12",
  "floors": 5, "victory": true, "reward": false,
  "completion_verified": true, "reward_verified": false,
  "strategy_training_eligible": false, "censored": true,
  "gift_picks": ["Wound Clerid"], "gift_keywords": ["Bleed"],
  "route_kinds": ["elite", "shop"], "shop_purchases": [{"name": "Polarization", "price": 158, "keywords": ["Bleed"]}],
  "skill_replacements": [{"sinner": "Yi Sang", "skill_id": 1010102, "replaces": 1010101, "price": 77, "delta": 8.0}]
}
```

Invariants, all enforced:

- `progress`, when supplied, must equal `20 * floors + 10 * victory + 10 * reward`; a disagreeing
  number is malformed input.
- A claimed `victory` requires `completion_verified`; a claimed `reward` requires `reward_verified`.
- **Only `strategy_training_eligible and not censored` outcomes reach the learned weights.**
  Everything else still counts as an episode and as evidence, and contributes exactly zero learning.
  This matches `mirror_assessment.assess`, which is the module that decides eligibility and reports
  `strategy_training_eligible` plus its `limitation` field.
- The input state is never mutated (`update_outcome` works on a deep copy), and `model_trained`
  stays `False`.

`knowledge_base_for(outcomes, state=None)` folds a list in the order given.

`policy_summary(knowledge_base=None)` renders the current state as a stable, presentation-ready
summary: version, episode and eligibility counts, per-space weights, sources, `model_trained`, and
the limitation string.

## Wiring suggestions (not implemented here)

This module stops at policy. Nothing calls it yet, and nothing below has been done.

1. **Learned labels into mirror decisions** (`PROJECT.md:1421`): the reader side already produces
   gift names and keywords. Call `gift_utility` per candidate with the plan from `load_gift_plan` and
   the keyword map from the current `knowledge_base['weights']`, then let the existing floor-gift
   chooser order by `score` while recording `static_score`/`learned_score` in the run record. No new
   authority is created: the plan and the block list still decide what is *allowed*.
2. **Episode feedback**: after a run, build the outcome object from `mirror_assessment.assess`'s own
   fields (`floors`, `victory_verified`, `reward_verified`, `strategy_training_eligible`) plus the
   run record's actual picks and purchases, then call `update_outcome`. Keep the result in the run's
   evidence directory as JSON; do not write to any private ledger.
3. **Shop**: use `shop_vision.offers` / `currency` / `refreshes` for reading and `shop_plan` for
   ordering, so the plain-refresh budget stays `settings.shop_refreshes` (default 2) and the plan
   order stays purchase Confirm, planned offer, bounded refresh, Leave.
4. **Skill replacement**: wire `skill_replacement` as the *gate* in front of any existing replacement
   click. If it refuses, the click must not happen and the refusal code plus `evidence` must be
   recorded. The five required inputs (sinner, complete caption, price, displaced slot, successor)
   must come from independent reads.
5. **Route**: replace the ordering half of the plan with `route_score` only after
   `route_plan.plan_route`'s identity preconditions are met; keep the identity refusal as the outer
   guard.

## Verification

`tests/test_mirror_learning_policy.py` — 159 tests, all passing —
covers the shipped catalog and gift plan, caption auditing, the static/learned split on every
surface, refusal codes, JSON safety, determinism, and the input immutability of
`update_outcome`. Evidence is recorded in `build/deepseek-mirror-learning-handoff.json`.
