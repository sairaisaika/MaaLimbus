# The shop's way back for a dead key Sinner

This document describes the one shop service this project spends on for the run's own sake:
`Heal Sinner`, the modal it opens, the Sinner it brings back and the receipt that books the
purchase. It is a **service** document — the shop's shelf, its refresh and its carry cap stay in
`docs/shop-settings.md`.

Module: `src/maalimbus/shop_revive.py`. Planner: `src/maalimbus/window.py:557-593`, `:615-626`,
`:988-1001`. Runner: `src/maalimbus/runner.py:1823-1867`, `:2031-2081`. Receipt store:
`src/maalimbus/deployment_transaction.py:69-92`. Tests: `tests/test_shop_revive.py`,
`tests/test_runner.py`, `tests/test_vision.py`, `tests/test_window.py`,
`tests/test_deployment_transaction.py`.

## The rule and the route

The operator's standing rule and the route they gave for it (2026-10-12):

> a Sinner in the first seven slots of the saved order who cannot be deployed has to come
> back; `Heal Sinner 100` opens three options and **the third one is the revive**, and then
> the Sinner itself is the one that has to be clicked.

Read as steps, the whole route is:

| Step | Page | The page prints | What the plan clicks |
| --- | --- | --- | --- |
| 1 | `SHOP` | the `Heal Sinner` service in the left panel | the service's own label box (`src/maalimbus/runner.py:1854-1866`) |
| 2 | `HEAL_SINNERS` | `Heal Sinners`, three numbered ways, `Return` bottom-right | the third row, `3. Revive a single Sinner.` (`src/maalimbus/window.py:988-1001`) |
| 3 | `REVIVE_PICK` | `Select the Sinner to revive.` | the dead card's portrait in the party bar, then the modal's own `Select` (`src/maalimbus/window.py:568-593`) |
| 4 | `REVIVE_DONE` | `<Sinner>, revived, returns to battle.` | the modal's own `Leave` (`src/maalimbus/window.py:557-567`) |

Measured live on 2026-10-12 with `Heal Sinner` priced at 100 and the shop's counter at 3093:
step 2 sent the third row, step 3's portrait click selected Hong Lu (the dead card 6), the
modal's own `Select` spent the 100, and the next read printed `Hong Lu, revived, returns to
battle.` over 2993.

## The three pages, each named from what it prints

The modal is not a menu the run may walk blind: the option rows answer nothing until the modal's
own bottom-right button is pressed, so each state is a page with its own input. Recognition lives
in `src/maalimbus/vision.py:266-288` and the words are locale keys in
`assets/resource/en/locale.json:67-69`:

| Page | Proof 1 | Proof 2 | Live frame |
| --- | --- | --- | --- |
| `HEAL_SINNERS` | `^Heal Sinners$` in `(.08,.02,.30,.12)` | three ordinal rows, the third with its own badge (`heal_sinners_options`) | `evidence/runtime/window-20261012-213008/frame-0001.json` |
| `REVIVE_PICK` | `^Select the Sinner to rev\S{1,3}e\.?$` in `(.04,.51,.25,.58)` | the `Heal Sinners` title above it | `evidence/runtime/window-20261012-214635/frame-0006.json` |
| `REVIVE_DONE` | `^.+ revived, returns to battle\.?$` in `(.03,.51,.30,.58)` | `^Leave$` in `(.80,.85,.96,.94)` | `evidence/runtime/window-20261012-214803/frame-0001.json` |

Each page needs **two** independent tokens, so the title alone does not name the modal and a
notice alone does not name the end state. The struct is the second proof for `HEAL_SINNERS`
because the live OCR reads the first option's ordinal as `I.` rather than `1.` — which is why
`ORDINAL = re.compile(r'^\s*[0-9Il|]{1,2}\s*[.,:]\s*\S')` (src/maalimbus/shop_revive.py:118)
matches a glyph run and the rows are taken in reading order.

`modal_bottom_control(records, patterns)` (`src/maalimbus/shop_revive.py:220-233`) reads that one
bottom-right control from the word it prints inside `CONFIRM_X=(1560,1860)` ×
`CONFIRM_Y=(900,1010)`: `Return` [1610,941,172,55] in the three-way step, `Select`
[1614,937,166,61] in the pick step and `Leave` [1622,943,150,53] after a revive. Exactly one
token has to match, so a frame that prints two of the words is refused rather than clicked.

## Which Sinner is dead — never from the picture

The dead slot is the deployment page's own proof, never a portrait's look:

```
saved_order(store)        -> store["saved_order"] or store["order"]   (shop_revive.py:262-266)
unavailable_sinners(store)-> store["unavailable"], its rejected inputs' proofs' cards,
                             and each rejected intent's card, minus the booked revives
key_losses(unavailable, saved_order) -> the unavailable cards inside the first KEY_POSITIONS
```

`KEY_POSITIONS = 7` (`src/maalimbus/shop_revive.py:23`) is the operator's rule; a card that came
back earlier is dropped from `unavailable_sinners` by the `revives` receipts it wrote, so a
Sinner is never bought back twice.

The picker's bar is measured geometry, not a search: twelve hexagonal portraits at a 115 px pitch
with the first slot's centre at x 112 (`BAR_FIRST_CENTER=112`, `BAR_PITCH=115`, `BAR_TOP=880`,
`BAR_SIDE=90`, `BAR_HEIGHT=120`), so `slot_box(card)` is `[112 + 115*(card-1) - 45, 880, 90, 120]`
and `picker_slot(unavailable, saved_order)` is that box for `key_losses(...)[0]`. The dead slot
carries the game's own red `0` and is the one number this OCR never reads, which is exactly why
the slot comes from the deck the page was drawn with.

## The receipt: planned, then proven by the shop's own counter

A revive is the one shop input whose price the run cannot read off the shelf before it is spent,
so it is booked only against a delta:

1. `runner` plans the service and stores `state['revive_receipt'] = {card, cost, coins_before}`
   with `coins_before` from the shop's counter on that frame, noting `shop_revive_planned`
   (`src/maalimbus/runner.py:1860-1866`).
2. On the next `SHOP` frame it consumes the receipt: the game's `currency` must be exactly
   `coins_before - cost`. Then `book_revive(card, cost, coins_before, coins_after, proof)`
   appends `{card, cost, coins_before, coins_after, proof}` to the store's `revives` and persists
   it (`src/maalimbus/deployment_transaction.py:73-92`), noting `shop_revive_booked`.
3. Any other delta notes `shop_revive_receipt_not_proven` with
   `the_shop_s_counter_did_not_show_the_revive_price` and books nothing. `book_revive` itself
   refuses a card outside 1..12 and any record whose `coins_before - coins_after != cost`, so a
   revive the run cannot prove can never make the next shop believe a dead slot is fieldable.

## Scope: what this does not do

* It does not heal. `Heal again.` and the modal's two heal rows are deliberately never targets;
  only the revive row and the modal's own bottom button are, and both are read from what the
  frame prints.
* It does not pick a Sinner by appearance and does not search the bar. A picker whose proof names
  no lost card is refused (`the_picker_asked_for_a_sinner_no_proven_loss_names`), and so is a
  notice without a bound `Leave` (`the_revived_sinners_notice_has_no_bound_leave`).
* It does not decide that a revive is worth its price. It answers the operator's rule; whether
  the run was better off spending the 100 elsewhere is a judgement this module does not make.
* It does not touch the carry cap, the shelf, the refreshes or the budget: the revive is paid out
  of the run's in-run currency, so it cannot move the module gate's budget.
* It does not claim the receipt is a game log. It is the shop's own currency delta, hash-bound to
  the frame it was planned on via `proof={'source': 'shop_currency_delta', 'image_sha256': ...}`.

## Verification

```
python -m pytest tests/test_shop_revive.py tests/test_vision.py tests/test_window.py -q  # 134 passed
python -m pytest tests -q                                    # 1598 passed, 1 skipped (Windows symlink permission)
python tools/make_local_app.py                               # dist/MaaLimbus, self_test + agent_self_test true
```

The live route was measured frame by frame, not only in tests:

```
window-20261012-213008   the three-way modal (Heal Sinners, 3093) and, one step later, the picker
window-20261012-214600   clicking the picked portrait again takes the pick back (227 px -> 0);
                         the option rows, the 100 badge and the inner row do nothing
window-20261012-214635   the pick step's own Select [1614,937,166,61]
window-20261012-214803   'Hong Lu, revived, returns to battle.' over 2993 (= 3093 - 100) and Leave
```

The planner has since driven parts of this route in one window each:

```
window-20261012-221139  build/deepseek-revive-live-14.json, started on the notice itself:
                        step 0 REVIVE_DONE -> SHOP, the_revive_is_paid_for_and_the_modal_leaves_back_to_the_shop
window-20261012-221631  build/deepseek-revive-live-15.json, 70 steps, 0 failed, no stop: the whole
                        shop visit (two carry-cap purchases, the exit) and then the live dungeon
                        (battles, EVENT_CHECK, REWARD_CARD, GIFT_PICK, the floor theme pack)
```

What is **not** covered yet: a single live window starting at `HEAL_SINNERS` and carrying the revive
itself through `REVIVE_PICK` and `REVIVE_DONE` — only those legs are live-proven, not that one run.
The carry-cap spend of `docs/shop-settings.md` was proven live in the run above (2993 -> 2400).
