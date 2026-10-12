# Shop shelf and skill-replacement reader (offline)

`src/maalimbus/shop_skill_vision.py` reads two screens it never touches a device to see:

- `read_shelf` — what the Mirror Dungeon shop shelf is announcing and at what price.
- `read_subpage` — what an *opened* skill-replacement subpage proves about one swap.

Neither call spends anything, clicks anything, or captures anything. `authorized` and
`would_spend` are always `False`; durable intents and every input stay in
`shop_transaction.ShopTransaction` and the runner.

## What this module does not claim

- **No live subpage capture is retained in this repository.** The replacement subpage's
  layout is therefore *unknown*: this reader does not assume a layout, does not infer a
  slot from geometry or slot index, and returns `complete=False` on any real subpage
  frame by design. `live_subpage_evidence` is always `False`; only `subpage_dict(...,
  synthetic=True)` can raise the synthetic flag, and nothing can clear it.
- **No model is involved.** `subpage_dict` reports `model_trained=False`; there is no
  learned component in this file.
- **No purchase is ever approved.** A `complete=True` reading is a *bounded question that
  the page answered*, not permission to spend.
- **No threshold is tuned here.** `DEFAULT_THRESHOLD` is `.9` and it is only ever the
  caller's number. A field below it is reported as `*_below_threshold`, never rounded up.
- One live shelf frame *is* retained, and it is the only live evidence:
  `evidence/runtime/window-20261012-024300/frame-0173.json` (+ its sibling PNG, whose
  SHA256 the reader carries).

## Reading the shelf: who is the offer for?

A replacement offer announces itself in its own printed words — `Replace <sinner>'s
Skill`. The sinner comes from **that text and nothing else**. The card's column, grid
slot, or index never decide who the offer is for; they only pair the announcement with
the price badge printed under it in the same column.

Measured facts that shape the reading (from the retained frame):

| Fact | Value |
| --- | --- |
| Announcement | `Replace Heathciffs Skill`, confidence `.979651` |
| Price | `77` (integer), confidence `.834838` — **below `.9`** |
| Gift titles on the same shelf | `Curriculum Vitae`, `Polarization`, `Prejudice`, `Scalpel`, `Uncapped Defibrillator` |
| Name rows / price rows | names y=496..530; badges y=458..494 and y=688..724 |
| Pairing tolerances | `COLUMN_TOLERANCE=90` px, `PRICE_ROW_BAND=90` px |
| Shelf band | x 820..1860, y 280..830 |

`REPLACE_PATTERN` deliberately allows the possessive to be missing or mangled: the
retained frame prints `Heathciffs`, and a dropped `'s` was measured to make a canonical
offender like `Replace Ryoshu Skill` vanish entirely. Widening the pattern can only turn
a silent miss into an honest `sinner_text_not_a_canonical_name` row, because the captured
token is then matched **exactly** against `storage.SINNERS`. `Heathciffs` therefore stays
unreadable; it is never rounded onto `Heathcliff`.

`Shelf` carries, per offer: `sinner`, `sinner_known`, `announced`, `announced_confidence`,
`name_box`, `price`, `price_confidence`, `price_box`, `column`, `reasons`, `ambiguity`.
A missing badge is `price_pair_missing` + `price_unknown` (**not** a price of zero); two
badges in one column are `price_pair_ambiguous` and the first is not preferred; a stray
one- or two-character fragment (the retained frame has a stray `C`) is OCR debris, not a
gift title.

### Frame identity

`FRAME_FIELDS = ('scene', 'size', 'image_sha256', 'ocr')`. `read_frame` refuses a frame
missing any of them, refuses an OCR box outside the image, and refuses a `.json` whose
sibling `.png` hash disagrees with the frame's own `image_sha256` record — a partial or
mismatched read could otherwise look like a clean shelf. The suffix is replaced on the
*name*, not the dotted stem, so `frame-0173.200.300.json` still finds
`frame-0173.200.300.png`.

`_size` accepts the 1920x1080 reference layout or a proportional rescale (a 0.5 px
rounding allowance, so `1000x562` reads and `1920x1079` is refused). Every region is a
normalized box over 1920x1080, so a different aspect ratio would silently shift them.

## Reading the subpage: the bounded question

`read_subpage` answers **exactly one** skill: the one the shelf already announced. The
caller supplies the question; the reader only confirms whether the page proves it.

```
read_subpage(records, size=None, *, identity_id, skills, skill_id, name,
             skill_names=(), replaces=(), price=None, threshold=DEFAULT_THRESHOLD,
             confirm_roi=None, cancel_roi=None)
```

| Argument | Meaning |
| --- | --- |
| `identity_id` | integer id from `identity-catalog.json` |
| `skills` | the skill-id set the same catalogue binds to that identity |
| `skill_id` | the announced skill's id |
| `name` | the name that skill is printed under |
| `skill_names` | `{skill_id: printed name}` — resolves the **displaced** skill's name |
| `replaces` | skill ids that may be displaced on this subpage |
| `price` | the integer price already read off the shelf |

Rules, in the order the reader applies them:

1. Only the **announced** name is searched for. An unannounced skill's name simply not
   being on the page is not a missing field and does not block the reading.
2. A name that is not on the page is a missing field (`skill_name`,
   `replacement_slot:<id>`) — never evidence about some other skill's row.
3. Every resolved id must be bound to the identity by the shipped catalogue, so a page
   can only ever confirm ids that already exist (`skill_not_bound_to_identity`,
   `replacement_slot_not_bound_to_identity`).
4. If `replaces` is non-empty and exactly one displaced name resolves, that is the slot.
   Zero or several leaves `replacement_slot` **missing** and `replaces=None`: an
   unresolved slot is never a licence to displace anything.
5. A slot that resolves to the announced skill itself is `replacement_slot_is_the_new_skill`.
6. A price is accepted only if it is printed (or, when supplied by the caller, actually
   present in the OCR rows). Two printed prices are `price_ambiguous`; none is `price`.
7. The Confirm/Cancel pair defaults to the shop's own dialog regions
   (`shop_vision.CONFIRM_ROI` / `CANCEL_ROI`); anything but a unique `.9` pair is
   `confirm_cancel_pair_unproven`.
8. `complete` requires a resolved skill id, a resolved slot, a price, and no `refused`
   and no `missing` entry.

`subpage_dict` emits `authorized=False`, `would_spend=False`, `synthetic`,
`live_subpage_evidence=False`, and the full `evidence` list (field, text, box, confidence).
`SUBPAGE_PROTOCOL` (`--print-protocol`) states all of this before any page exists, so the
runner can declare the contract and a synthetic fixture can never be mistaken for a
validated layout.

## Catalogue

`load_identity_skills(path)` returns `{identity_id: set(skill_id)}` from
`assets/resource/base/identity-catalog.json` (version 1, a *list* under `identities`).
The catalogue is the only source of skill ids here: no second numbering, no invented id.
A row without an integer `id` or a non-empty integer `skills` list raises `ValueError`.

## Reading the notice that covers the shelf

A real purchase does not return to the shelf: the game raises the native
`E.G.O Gift GET!` notice over it, so the shelf that proves the coin delta is behind the
notice and the run used to stop with `shop_receipt_successor_not_proven`.

`read_overlay(records, size, scene=..., require_scene='GIFT_GET', ...)` and
`frame_overlay(path, require_scene='GIFT_GET')` recognise the notice by the two texts the
project already proved in `assets/resource/base/anchors.json` (id `gift_get`): the title
inside `GIFT_GET_TITLE_ROI` and its single `Confirm` inside `GIFT_GET_CONFIRM_ROI`, both
at the observed threshold. Measured on the one retained frame in this workspace
(`evidence/runtime/window-20261006-042640/frame-0066.json`): title `E.G.O Gift GET!` at
`[828, 250, 258, 41]`, `Confirm` at `[922, 774, 136, 45]`, both recorded as constants
because they are measurements of a retained frame, not an invented layout.

The returned card distinguishes three states and never blurs them:

- `available=False` — this frame is not the notice (`overlay_scene_not_gift_get`,
  `overlay_absent`), a tolerated read.
- `available=True, complete=False` — the notice is up but unread
  (`overlay_confirm_not_proven`, `overlay_confirm_ambiguous`,
  `overlay_title_ambiguous`, `overlay_title_differs_from_proved_notice`); `target` is
  `None`, so nothing may be clicked.
- `complete=True` — exactly one proved title and exactly one Confirm; `target` is the
  notice's own Confirm box. Read as evidence only: `authorized`, `would_spend`,
  `input_sent` and `game_controller` are all `False`.

A locale may widen the title *pattern*, but a wider match must still normalise to the
proved notice title, so a localisation cannot turn an unrelated page into a notice.

## Wiring, and what stays outside

1. Call `read_shelf(frame_ocr_rows, size, source=frame_path)` after the runner has
   recognized the shop page. Take the sinner from the returned `SkillOffer`, never from a
   card position.
2. Pair the offer with `shop_vision.offers(...)`/`currency(...)` for affordability. This
   module does not decide affordability — `mirror_learning_policy.shop_offer` does.
3. On `price is None` or `sinner_known is False`, do not click. Record the reason row.
4. Open the subpage, then call `read_subpage` with the announced id/name and the
   catalogue's skill set. `complete=True` means the page answered the bounded question;
   the spend policy (budget, `shop_replacement_budget`) still decides.
5. Store `subpage_dict(...)` output as evidence next to any replacement intent in
   `shop_transaction`.
6. Re-read the shelf after a refresh. A frame whose PNG hash disagrees with its record is
   refused, so a stale capture cannot be replayed as a fresh one.
7. When the page after a reserved purchase `Confirm` is the notice, call
   `shop_transaction.ShopTransaction.reserve_overlay_acknowledgement(scope, visit,
   frame_path)` **before** sending anything. It re-proves the notice, binds the
   acknowledgement to the notice frame's own PNG hash, refuses a frame that repeats either
   retained frame, records the intent at stage `overlay_intent`, and returns the notice's
   own Confirm box to click. A restart can never send it twice.
8. After that click, wait for the shelf itself. A purchase is still receipted only by
   `reconcile_purchase`, which needs the returning shelf with the exact coin delta and the
   removed offer; the notice is an input anchor, never a receipt.


## Verification

`tests/test_shop_skill_vision.py` — 32 focused tests (one parametrized), all offline, covering the retained
frame's own values, the mangled sinner name, missing/duplicate/low-confidence badges,
column pairing, debris fragments, frame-field and PNG-hash refusals, the catalogue binding,
the full subpage refusal vocabulary, the synthetic flag's one-way behaviour, and the
protocol declaration.

`tests/test_shop_receipt_acknowledgement.py` — 15 focused tests pinning the notice path:
the retained live frame read to its exact measured boxes, the unread and ambiguous
refusals, the locale pattern that cannot widen what the notice may say, the tampered
retained frame, the one-shot acknowledgement bound to the notice's own PNG hash and
replayed-frame refusal, a restart that cannot acknowledge twice, the shelf that still has
to prove the coin delta, and six unread/unearned notices that leave the pending intent
byte-identical. Run:

```
python -m pytest tests/test_shop_skill_vision.py tests/test_shop_receipt_acknowledgement.py -q
```

The generated verification + handoff record is
`build/deepseek-shop-skill-handoff.json` (regenerate with
`python build/tools/make_shop_skill_handoff.py`).
