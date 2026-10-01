# Native design and requirement ledger

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
