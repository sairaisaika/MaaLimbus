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

This model has unit coverage, but the six native task entries, MXU global/settings
panels and their live integration are still pending. No unimplemented task is
reported as supported or accepted because its button exists. The native PI V2
global_option and setting section protocol in the pinned MaaFramework source is
the UI contract to use rather than a separate Lix frontend.
