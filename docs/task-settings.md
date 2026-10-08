# Tasks and saved builds

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
