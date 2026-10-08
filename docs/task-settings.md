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

The six main task entries, task reference/rotation UI, visual global-editor
restart verification and full live integration are still pending. No unimplemented task is
reported as supported or accepted because its button exists. The native PI V2
global_option and setting section protocol in the pinned MaaFramework source is
the UI contract to use rather than a separate Lix frontend.
