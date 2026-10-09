# Tasks and saved builds

## Interactive native client

The project-owned pinned-MXU overlay renders saved builds as a twelve-sinner
formation grid. Click order sets deployment badges; click again removes a sinner,
clear resets the draft, and arrows move an existing choice. Save requires twelve
distinct known sinners and persists all order/name/system UI values together.
Other build preferences remain unchanged. Backend application still validates
the whole edited batch before the Mirror task; active-run team edits reject.
Failed persistence restores the previous UI values. Browser preview is UI evidence,
not installed native restart or game deployment proof.

Software updates have their own settings section with current version, automatic
startup updates, explicit GitHub check and retry status. Manual checking uses the
same persistent rate-limit/cache state and never installs, restarts or drives the
game. Device connections have a separate section using MXU's existing native
discovery/connection component. Modified client builds retain the complete pinned
upstream and project-patched corresponding sources and reject stale artifacts.

The requested main task list is: open game, Mirror Dungeon, experience
luxcavation, thread luxcavation, collect rewards, and stamina conversion.
Battle assignment, theme packs and deployment are preferences within Mirror
Dungeon rather than standalone tasks. Existing diagnostic entries remain until
the new task entries and UI have been verified; they are not the final UX.

Global saved builds remain in `config/user-team-profiles.json`: named team slot,
ordered sinners and keyword systems. A task references a slot, never stores a
second character roster. Team editing must be interactive and persist across a
GUI restart. Existing deployment evidence and imported LALC builds are retained.

`TaskPreferences` stores the independent task choices in `user-task-settings.json`:
Mirror difficulty defaults to hard; single team or an ordered rotation can be
selected. Experience and thread luxcavations each reference a saved default team.
The model reloads the global build on each task resolution so a user's next edit
to that team takes effect without repeating it in each task. Unknown slots,
duplicate rotations and inconsistent single-team settings reject without replacing
the previous configuration. Existing active-run ledgers must not change queue mid-run.

Native MXU `setting` sections now offer 20 independently named build editors,
each with a system selector (including Charge + Tremor and Burn + Tremor) and
twelve sinner dropdowns. The default keeps existing saved builds. Explicit edits
are applied before MirrorLoop, after validating every edited build together;
duplicate sinners and editing the active run's team stop without partial writes.
Other fields such as gift allow/block lists and theme preferences are preserved.
MXU saves UI option values immediately through its own settings persistence;
ProfileStore receives validated edits when the Mirror task starts. Native Maa
resource replay proves 30 independent option patches preserve two whole builds
and inactive editor fields do not apply. This is not GUI interaction verification.

Ordinary MXU task overrides replace each node's action params shallowly. Editors
therefore use distinct inert nodes with native `attach` metadata, rather than
assuming nested action-param patches will deep-merge. An invalid run ledger now
stops the loop before game input instead of allowing bookkeeping to be skipped.

Mirror now references global builds through keep-current-rotation, single-team,
or ordered-rotation selectors. Rotation length is 1..20 and positions are fixed
team dropdowns; only the selected length applies. Changing the queue during an
active run rejects without replacing ledger/preferences. Idle changes preserve
completed receipts and retain the next saved team when it is still in the queue.
Native resource replay proves the single-team and five-team parameters; actual
new Mirror UI task dispatch and next team entry remain pending.

Actual native GUI opened, displayed global Team2 editors, persisted edit mode,
and was restored to keep-saved without starting a task. A local-only migration
then seeded the saved private order/name/system after normal GUI exit, retained
a configuration backup and copied 12 missing private state files into the local
app. Existing customized editors are preserved. Team2's seeded order matches
3,4,9,1,7,2,12,5,8,10,11,6. A fresh GUI restart loaded the installation, but the
new order's visible dropdown/restart acceptance is still pending. Private data
is not part of public package assembly.

The six main task entries, visual saved-order restart verification and full live
integration are still pending. No unimplemented task is
reported as supported or accepted because its button exists. The native PI V2
global_option and setting section protocol in the pinned MaaFramework source is
the UI contract to use rather than a separate Lix frontend.

Local development installations now have an explicit private `config/user-data-root.json` binding to the source configuration directory. Agent builds, progress transactions, launch preferences and config-relative ledgers resolve this single directory, including when MXU supplies the installation config environment. The binding tool requires a closed development app and disabled autorun/tasks, backs up both original state directories, and does not overwrite either ledger. Missing, chained or linked targets fail before input. Public packages do not contain this private binding; their state remains installation-local. Actual binding preserves entered Team7 scope4734; native dispatch with the refreshed Agent remains pending.

Six main task entries now route through a shared native task action and controller lease. Mirror delegates to the same runner after global settings apply; diagnostic team/theme/deployment/card entries are no longer main tasks. Luxcavation team selectors independently reference saved builds and preserve the active Mirror ledger. Android open-game uses a durable once-only native launch intent, independently confirmed foreground, and leaves an already running game intact. Windows validates the existing connected game. Actual OpenGameTask observed MuMu already foreground, with a retained STAR_GRACES screenshot and unchanged active ledger; cold launch is not yet accepted. Experience/thread stage and cost policies, mail/daily collection and conversion remain under development: those routes currently capture evidence and return failure without input. Their presence is not functional task completion. Native resource parsing/option overrides passed without a controller; the six-entry GUI render/restart is still pending.

Actual installed native GUI now visibly lists the six task choices and Mirror saved/single/rotation modes. The QA card is disabled, mode restored to saved, and autorun remains off. Source rotation-count options now activate only positions1..N, instead of exposing twenty fields when N is five. Source native parsing and16focused checks passed; the new conditional display is awaiting installation/visual verification.

Mirror starlight rules are task-local native MXU options. Keep-current is the
safe default. Follow-team loads the saved build's Lix zero-based 0..9 choices
and explicit starlight cap whenever that team runs; follow-task uses this task's
choices/cap for all referenced teams. The Mirror section includes an explicit
saved-team star editor, preserving that build's name, systems, deployment and
other preferences. Applying an edit to the active run's team rejects before input.
Old imported builds without a cap must receive one before follow-team can spend.

Automatic selection uses the current saved team's priorities, or the task list
when that build has none, and the smaller applicable task/team cap. It reads the
current visible prices and available balance, freezes one affordable priority
subset before purchase, and persists the scope and intents. It does not infer
seasonal buff strength or use a static price table as purchase authority. Changed
prices, unknown balance and unverified pending inputs stop; restarting does not
re-budget or repeat them. This is a bounded heuristic, not a learned optimum.
Only basic stars are supported: no Enhance or leftover conversion. The task
budget defaults to zero. Source/native isolated persistence checks are complete;
GUI rendering, installed editor restart and real automatic purchases remain
unverified. The existing desktop and v0.1.1 draft do not contain this change.
## Mirror task window options (October9)

The Mirror task now exposes initial-gift system, gift-search refusal and bounded
steps alongside saved/single/rotation teams and starlight settings. Each option
uses a separate inert native node so MXU shallow overrides preserve the other
choices. The Agent validates and merges all three into the actual MirrorLoop
parameters before constructing a runner. Defaults retain existing launch values;
an explicit initial system affects the initial tray only. Floor gifts continue
using the selected saved team's systems, allow/block lists and trial scoring.
Search refusal never authorizes a paid search. Steps are a per-launch bound, not
a dungeon repeat count. These additions are source/native-parser verified, not
yet installed or visually accepted. Battle-card and theme/gift preference editors
remain unfinished; this addition does not mark them complete.
## Mirror build preference editor (October9)

Mirror settings contain a saved-build preference editor, disabled by default.
Choose a saved team and add a catalog gift to allow/block lists or a catalog theme
to preferred/blocked weights. A preferred theme has an explicit weight25/50/75/100;
a blocked theme has weight0. Separate inert nodes preserve all choices through
MXU option patching. The whole edit validates before one atomic ProfileStore save
when the Mirror task starts. Existing lists, systems, deployment and star settings
remain intact; blocks retain precedence. Changed preferences for the active run's
team stop before gameplay, while identical reapplication is idempotent. Unknown
catalog names and malformed active ledgers reject without writing. This first
editor adds entries and adjusts named theme weights; removal/list management and
battle-card editing remain open. Native parsing and isolated profile persistence
are verified; installed rendering/restart and actual gameplay preferences are not.

Mirror saved-build preferences support explicit removal of a selected priority
gift, blocked gift or theme rule. Default keep changes nothing. A theme removal
removes its saved weight (including zero/block), restoring the existing neutral
runtime behavior. New/add and removal of the same entry in one batch refuse;
unknown identity or active-build change refuses before any profile write. Native
resource parsing and isolated persistence are verified; installed GUI interaction
and restart persistence remain open.

Mirror battle auto-assignment offers follow-launch, Win Rate, Damage and observe
(stop) as a task option. Defaults select Win Rate. Damage uses its independently
recognized button; missing Damage refuses without fallback. Observe sends no
battle input even with START visible. Automatic modes submit a currently assigned
turn when START is proven. This is the game's auto-assignment preference; it does
not implement an individual skill-order editor or infer a battle victory. Native
resource parsing and retained-frame plans are verified; live Damage execution
and installed GUI rendering remain open.


## Rewards task execution (October9)

The native rewards entry now dispatches a bounded Mirror payout executor instead
of the capture-only placeholder. It requires an already verified five-floor run,
its explicit current-scope module budget and freshly proven cost/weekly offer.
Each claim, confirmation, reward receipt and pass receipt gets a durable intent
before one input. Unknown pages, repeated intents and unsettled successors stop;
this task never starts a run, changes weekly bonuses or gives up the dungeon.

Payout bookkeeping requires all four scoped input reports, their PNG hashes,
actual receipt numbers and independent HOME evidence to pass the receipt audit.
Only then are reward/return recorded and the saved queue advanced. An interrupted
transaction write after rotation can recover from the exact archived event hashes
without another rotation or input. Device attempts remain reported even if input
or the successor read fails. Mail/daily collection, experience/thread farming and
stamina conversion are still unfinished. Retained evidence and isolated state
verify this execution wiring; live current Team7 payout and native GUI dispatch
are not accepted, and no current paid input is authorized by those tests.
