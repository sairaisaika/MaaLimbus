# Native design and requirement ledger

## Deployment reset and inherited selection (October8)

Before selecting a saved order, a nonzero inherited participant count requires a
fresh ClearSelection caption. This is an identity anchor and must be bound from
the current page, not guessed from the static control list. The real game asks
ResetDeploymentOrder before clearing. Persist the clear intent, then persist
confirm_sent before one scoped confirmation. Only actual0/capacity resolves it;
unknown frames or unchanged counts keep the pending transaction and stop input.
Card selections require exact+1 counts. Crash recovery requires the same scope,
expected count and selected/backup caption on the exact pending card. The native
numeric-only counter crop is consulted only on independently identified prebattle
pages; whole-screen OCR dropping a numerator never justifies another click.
Pause-menu Settings/Resume independently veto behind-modal battle controls. This
observed English menu grants no automatic retry/give-up action. Japanese menu
localization remains unverified and is outside these English live proofs.

## Map node vocabulary and upstream comparison (October6)

The map panel is a boss-cell grid, not the six-slot option grid LALC models. Pinned
LALC 431b432 keeps two trained classifiers: `mirror_legend` (eight node classes:
abnormality/boss/elite/focused/regular encounter, event, shop, empty) and
`mirror_path` (nine `00..22` cells, six regions used, `connections.txt`). Its
`get_mirror_path` masks and *graffiti-fills* those six regions before inference, so
its model reacts to the highlighted option cells, not to the map nodes themselves.
A read-only comparison (`tools/compare_lalc_map_regions.py`) samples those regions
at the 1440x810 authoring scale and their half-scale projection; on the retained
floor-1 page the six LALC slots sit in the dark upper-left quadrant while the drawn
nodes occupy a wider area, so LALC's coordinates are not this page's node
coordinates. Node identity therefore stays unproven and route stays a refusal. A
future live session must first click one observed node and record the successor
page to establish what the panel proves; nothing may be assumed before that.

## Map identity and bounded routing (October5 late continuation)

The map page is identified by text only: the localized `Exploring`/`Before Entry`
floor header inside the upper-left band plus the theme-pack line directly beneath
it. The pack line must sit in its own band and must not repeat the floor pattern;
a page carrying similar wording elsewhere is never promoted, and node artwork,
cover art, season icons and currency amounts remain non-anchors. A theme drag is
substantiated only when the fresh post-drag page is that map and its pack line
equals the pack this run planned; any other name stays unproven.

Routing stays a refusal until node identity exists. A next node may be planned
only when the page is an identified map, a single current-position marker is
proven, and exactly one unvisited candidate remains; otherwise no click target is
produced and the reason is recorded. The retained floor-1 frame has no provable
unvisited node, so routing there must keep returning a refusal rather than a
fabricated target.

## Pack input and initial receipt proof (October5 late continuation)

Theme selection drags a positively identified card downward using Maa Swipe,
randomized inset rectangles and480–680ms duration. Neither task success nor fresh
post-drag capture proves selection: ThemeObservation deliberately records selected
false until a real map postcondition is implemented. Validate geometry against
the retained actual Hard frame before continuing. Highlighted Hard mode may use
strict mode/header/Refresh OCR fallback plus detail geometry; conflicting mode
evidence fails closed. Cover color and artwork are not the mode identity.

Free initial receipt acknowledgement persists each intent and resolves only after
the next named receipt or both specific Owned icons with labels. Search refusal
requires0/3 or equivalent counter, explicit Refuse, then explicit Forgo modal.
Underlying search classification never overrides modal veto. Android controllers
must not execute Windows P-key battle planning; verified touch control is pending.

## User configuration and grace transaction (October 5 continuation)

Import Lix's local team data through a whitelist, preserving rotation slots,
ordered sinners, keyword/style and initial-gift priorities. Do not import its
input runtime. Optional automatic formation filters each sinner's owned/selectable
identities by requested keyword union and selects maximum actual level; equal-level
ties favor hybrid keyword coverage. Complete inventory or independently verified
descending-level ordering is required. Missing identity evidence stops selection.
This pure policy is implemented; native UI execution remains pending.

Grace indices follow Lix0..9, left-to-right then top-to-bottom. Current user's
1,3,4,6 are base-only. Read each configured cost and available balance through Maa
numeric OCR. Persist intent before input, then require fresh balance decrease before
adding a selected index. Pending/changed balances veto retries. Full selection and
budget must be verified again before Enter. The confirmation independently checks
the conversion checkbox and numeric Cost0; remaining starlight conversion is off.
All targets use inset boxes with350..750ms randomized delay. Structural card edges,
ordinal position and page control text replace seasonal icons/colors/buff prose;
changed geometry fails closed. Confirmation progress cannot be reset merely because
the process ended. A fresh page proves navigation only, not final resource settlement.

## User-facing task labels

| Task | Options |
| --- | --- |
| Hard Mirror Dungeon | Runs; saved teams and order; deployment order; team keyword; starting gifts; floor gifts; theme pack preferences; E.G.O/battle policy; claim rewards |
| Convert Enkephalin | Reserve stamina; maximum modules; conversion enabled |
| Refill Enkephalin | Disabled by default; allowed refill count; maximum Lunacy per session; daily limit; reserve Lunacy |
| Claim mail | Claim free mailbox rewards |
| Claim daily rewards | Limbus Pass missions; completed daily/weekly claims |
| Launch game | Existing Steam/Windows installation, independent task |

Controller: **Windows · Limbus Company**. Resource packs: **English**, **日本語**.
Global settings: human-paced click delay range; error behavior (leave at error / close game);
logs and evidence retention; GitHub update proxy, last checked version and next retry time.
Saved-team profiles contain stable slot + optional visible name, keyword(s), sinner deployment
order, gift allow/block lists, starting gifts, pack weights and battle preferences. Team order
advances only after verified run completion and reward acceptance, persisted atomically.

## Execution boundaries

Maa owns Win32 screenshots/input, recognition, graph scheduling and timeouts. Use public OOP
Python bindings (Controller/Resource/Tasker/Job), retain objects until jobs finish. No direct
process memory, injection, interception driver or private game API. Reference build docs describe
building Maa itself; this application consumes pinned public binaries instead.

Graph: home → Drive → Mirror Dungeon → stable Enter → difficulty/session confirmation →
saved team → deployment/star/starting gifts → theme pack → map → encounter/event/shop →
battle → floor reward/buff → next floor. Floor 5 victory → reward selection → reward receipt →
entry page → next team → next run. Map may pan; use current node/connection evidence rather
than season-specific cover art. Resume in-progress runs without discarding them.

Recognition uses local text or masked stable glyphs plus normalized geometry, never whole
cover/background. UI text differences live in locale overlays. OCR numerical amounts are
values, not page identifiers. Ambiguity triggers a bounded re-observation and evidence stop.
Windows input method must be verified against the running game; no assumption that background
messages work. Click positions are sampled inside an inset recognized box; delays are sampled
within configured bounds. Re-check page and resource policy immediately before sensitive input.

Like MaaEnd's published PI Win32 controllers, the packaged Win32 controller declares
`permission_required: true`. The developer launcher uses ordinary Windows `RunAs`
with interactive UAC consent, as LALC's updater launcher does. The application
does not approve/bypass consent. Identity/privilege and single-controller gates
remain active after launch. Maa `Seize` performs foreground mouse down/up; a
successful SendInput return is insufficient without the expected next page.

## Choice policy

LALC's floor gift order: unowned preferred keyword/allow-list → unowned other → owned.
Block-list wins over allow-list. Native ranking additionally reports every scored candidate,
rejects unidentified/disabled options and separates gifts from enemy buffs. User pack weights,
team synergy, floor/difficulty and encounter risk combine; ties have deterministic ordering.
Do not claim a universally optimal gift: the best choice depends on active team and inventory.
Enemy buffs have independent penalties; unknown buff effects are not silently treated as beneficial.
Hard bosses require clash/survival evidence; win-rate autopick alone is not a verified hard-clear policy.

## Resource and error behavior

Conversions spend only existing stamina above reserve; refill is an explicit opt-in budget.
No extraction, paid store or unlimited refill nodes. Read actual amount/cost and verify balance
change after confirmation. Failed/unknown amount recognition cannot authorize spending.
On error: stop scheduler, flush frame/events/terminal reason, then optionally close only the
bound game process. Closing is never a recovery step or proof of success; retain assistant/logs.

## Updates, network resilience, packaging

GitHub Release update: HTTPS + ETag cache; separate 404/no release, network failure and rate limit.
Persist Retry-After/X-RateLimit-Reset deadline, resume after deadline; bounded exponential backoff.
Downloads are staged, SHA-256 checked, unpacked with root/path/size guards, configuration preserved,
and installation is deferred until app/Agent stop. Offline gameplay must not depend on GitHub.
Windows x86_64 portable MXU/Agent/Maa package with notices and reproducible build metadata.

## References

- MaaFramework cc5fef675f42ca899e12bc4932ff37ac1278853c: README, LGPL-3.0;
  docs/zh_cn/4.1-构建指南.md, 4.2-标准化接口设计.md, 2.4-控制方式说明.md,
  3.1-任务流水线协议.md and 3.3-ProjectInterfaceV2协议.md.
- LALC 431b432e22f0b0da08b95d7c478fa213be20b3e8, AGPL-3.0:
  config/task/mirror.json, task_action/mirror.py (floor gift/pack/star choices),
  task_action/utils.py (saved team/deployment), config/task/battle.json and mail/reward.
- MaaFgoHelper: bounded native recovery, saved configuration, original install hashes,
  staged update/rollback, actual Maa offline replay and honest completion evidence.

Published sources: https://github.com/MaaXYZ/MaaFramework and
https://github.com/HSLix/LixAssistantLimbusCompany . Upstream checkouts are local ignored caches.
