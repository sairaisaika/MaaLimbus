# Boss-adjacent shop settings

This document describes the three Mirror settings that decide how a shop visit is bounded,
and the pure resolver that turns them into one decision.

It is a **settings** document. Nothing here executes a shop visit, clicks a refresh, or
spends anything, and nothing here is a learning algorithm. Reading the shelf, spending and
learning from hash-bound receipts all stay where they already are. This module answers one
question:

> given the stored settings and this launch's choice — what refresh limit and what coin
> reserve is the run allowed to use?

Module: `src/maalimbus/shop_settings.py`. Tests: `tests/test_shop_settings.py`.
Resolver: `resolve_shop_settings(saved, overrides)` — a pure function that returns a
JSON-safe decision card and writes no state.

## The three settings

| Field | Drop-down choices | Accepted value | Meaning |
| --- | --- | --- | --- |
| `shop_policy` | `saved`, `manual`, `learned` | one of those | Which rule bounds the shop spending. |
| `shop_refreshes` | `saved`, `0`, `1`, `2`, `3`, `5` | an integer **0–5**, or `saved` | Plain refreshes allowed per shop visit. |
| `shop_reserve_coins` | `saved`, `0`, `100`, `200`, `300`, `500` | an integer **0–500**, or `saved` | Coins kept back and never spent in a shop visit. `0` means *no reserve*, not "spend everything". |

The drop-downs are the UI's offered choices; the resolver accepts **any** integer inside the
range, so a stored value the drop-down does not list (for example 4 or 250) still resolves.
Values are **strict integers**: a string of digits (`"3"`), a boolean or a float is a
refusal, never a coercion.

`saved` is the default for all three and means "keep my stored choice". The option cases are
declared in `assets/interface.json` (`mirror_shop_policy`, `mirror_shop_refresh_limit`,
`mirror_shop_coin_reserve`) under the `MirrorTask` task, with labels in
`assets/i18n/en_us.json`, `assets/i18n/ja_jp.json` and `assets/i18n/zh_cn.json`.

Each option is backed by its own independent pipeline node — `MirrorShopPolicy`,
`MirrorShopRefreshLimit`, `MirrorShopCoinReserve` in
`assets/resource/base/pipeline/mirror.json`. They are inert carriers: recognition
`DirectHit`, action `DoNothing`, no `next`, and a single `attach` field. A case overrides only
its own node's `attach`, so choosing a shop setting can never shallow-replace the `MainTask`
or `MirrorLoop` action parameters. `tools/verify_pipeline_spec.py` checks exactly that (an
option's `pipeline_override` must name a real node, and this run reports
`ok — 0 problem(s)`).

The `learned` case carries **no** child option group: the existing gift allow/block editor
stays at its own entry point (`mirror_preferences`), and no second binding to it is
introduced.

### What `saved` resolves to when nothing was ever stored

`saved` follows the runtime's own pre-existing behaviour, so an install that has never opened
these settings behaves exactly as it did before they existed:

```
shop_policy         manual
shop_refreshes      2
shop_reserve_coins  0
```

The card reports this as `runtime_default_used`, or as `kept_launch_choice` when this launch
explicitly re-selected "keep existing". `RUNTIME_DEFAULTS` is the single place that records
the values.

## What `learned` means here

`learned` is a **bounding** rule, not a model and not a learning algorithm:

* It may only obey the player's own two hard settings — `shop_refreshes` and
  `shop_reserve_coins` — and the existing gift allow/block list. This module never raises,
  lowers or rewrites either setting.
* An **explicit** reserve is used exactly as written. Lowering it is the player's own
  decision and the card records it as a deliberate downgrade
  (`reserve_manual` + `reserve_floor_lowered_by_player`); raising it is
  `reserve_floor_raised`. What independent learning may never do is lower a floor the
  player set, and that guard belongs to the learned layer, which only reads these settings —
  the resolver cannot tell a learned write from a player's choice, so it does not guess.
* With no recorded samples the **rule fallback** applies — these settings, no observed
  adjustment — and nothing claims a model learned to buy anything.
* `learned_applied` is always `False`, because this pure resolver takes **no** decision of its
  own. `model_trained` is always `False`.

Anything that actually scores a shelf from real receipts and successor evidence runs outside
this module, under the run owner, where those receipts are hash-bound. `shop_settings_protocol()`
returns this contract as data, so a UI can state it before any setting is stored.

## What the resolver refuses

Malformed input is a refusal, never a silent default:

* a boolean, float, string-of-digits, negative or out-of-range value;
* an unknown `shop_policy` mode;
* an unknown field;
* a `saved`/`overrides` argument that is not a mapping.

```
ValueError: shop_refreshes must be the string "saved" or an integer 0..5 (got '3')
ValueError: shop_reserve_coins must be an integer 0..500 (got 501)
ValueError: shop_policy 'automatic' is not one of ('saved', 'manual', 'learned')
ValueError: overrides names unknown field 'nonsense'; the option fields are ['shop_policy', ...]
```

## Reading the three inert nodes

`collect(get_node, saved=None)` reads the three nodes through a caller-supplied accessor and
resolves them, so a runner can wire it with its own page reader. It only **reads**; it does
not run the nodes.

## Scope: what this does not do

* It does not read the shelf, click an offer, click a refresh, or confirm a purchase.
* It contains no learning algorithm and reads no receipt, sample or evidence input. Its
  signature is exactly `(saved, overrides)`.
* It does not identify a boss room. "Boss-adjacent" describes which shop visits the setting
  applies to; there is no boss detection here and no forced purchase before a boss.
* It does not write the ledger, the budget, the settings store or any other state.
* It does not extend the skill-replacement flow. Skill purchase is still incomplete, so no
  enabled control is declared for it here.
* It makes no claim about a game formula or an optimal purchase rule. The caps are the option
  sets' own ceilings.

## Verification

```
python -m pytest tests/test_shop_settings.py -q     # 53 passed
python tools/verify_pipeline_spec.py                # ok — 0 problem(s)
```

Offline and read-only. No controller is created, no input is sent, no install or Release is
produced, and no state is written.
