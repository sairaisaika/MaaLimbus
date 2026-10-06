# P0 gap: the mirror pipeline ends when the battle starts

Written 2026-10-06 (round 13) from the current tree; every number below was read
out of the repository in this session, not recalled.

## The gap

`assets/resource/base/pipeline/mirror.json` holds **88 nodes**. Its terminal
nodes (no `next` and no `on_error`) are:

```
InitialReceiptObserve, LimbusSafety, MirrorTeamEvidence, LimbusUnknown,
LimbusExpired, LimbusDefeat, ThemePackNormal, ThemePackBoundary,
DeploymentBoundary, BattlePlanBoundary
```

The last ten are deliberate (they are `Custom`/boundary nodes whose callback
decides), but one of them is not: the battle path is

```json
"BattleObserve": {
  "recognition": "DirectHit", "action": "Custom",
  "custom_action": "limbus_battle_observe",
  "max_hit": 1, "next": [], "on_error": ["LimbusUnknown"]
}
```

`BattleStartTurn` (`custom_recognition: limbus_scene`, `scene: BATTLE_HUD`,
`battle_mode: start_turn`, `action: Click`, `target: true`, `next:
["BattleObserve"]`) is therefore the end of the line: the run stops there,
before the encounter reward card, the floor gift, the next floor and the run
end. Everything after the battle is implemented on the Python side
(`src/maalimbus/window.py` plans for `REWARD_CARD`, `GIFT_PICK`, `GIFT_GET`,
`SHOP`, `SHOP_LEAVE`, `EVENT_*`, `MAP`, `NODE_PANEL`) but nothing routes the
pipeline into it.

## What the pipeline may use (verified inventory)

* 13 custom hooks are referenced by `mirror.json` and every one of those names
  appears in a Python source (verified by `tests/test_pipeline_scenes.py`;
  `agent/main.py:40` is the registration point for `limbus_scene`, via
  `AgentServer.register_custom_recognition`), and `tools/*_replay.py` exercises
  them against archived frames:
  `limbus_battle_observe`, `limbus_battle_plan_observe`,
  `limbus_deployment_proof`, `limbus_difficulty_proof`,
  `limbus_initial_gift_proof`, `limbus_initial_receipt_proof`,
  `limbus_map_observe`, `limbus_preflight`, `limbus_scene`,
  `limbus_star_proof`, `limbus_team`, `limbus_terminal`, `limbus_theme_observe`.
  `tests/test_pipeline_scenes.py` now fails if a node names a hook that no
  Python source mentions.
* Scene names accepted by `limbus_scene` are frozen in that same test file (21
  names) and each must be mentioned by the agent side.
* Node schema in use: `recognition: Custom` + `custom_recognition:
  limbus_scene` + `custom_recognition_param` (`scene`, plus optionally `token`
  / `roi` / `battle_mode`), `action: Click|Swipe|Key|Custom`,
  `post_delay`, `timeout`, `max_hit` (mandatory for plain input actions, exempt
  for `Custom`), `next`, `on_error`.

## Why the next floor is not wired yet

Adding nodes is cheap; adding *unverified* nodes is not: an invented
`custom_action` name only fails on a live run, and this account is currently
soft-locked (see below), so a new route cannot be exercised end to end. The
honest sequence is:

1. reuse hooks that are already proven on the live device
   (`limbus_map_observe`, `limbus_scene` + `Click`, `limbus_terminal`);
2. add one post-battle node at a time and replay each against the archived
   frames in `evidence/runtime/` with the existing `verify_*_replay.py`
   pattern before it goes into `mirror.json`;
3. keep every new input bounded (`max_hit`) and route failures to
   `LimbusUnknown` rather than looping.

## Constraints that outrank finishing this

* single controller; MuMu touches only through Maa (`post_click`/`post_swipe`),
  never the desktop mouse;
* never click `Halt Exploration`, never restart the game client, never buy or
  convert anything (`assets/resource/base/budget.json` ships as `status:
  pending`, `module_budget: 0`);
* a stalled run is reported and stopped, not retried blindly.

## Current live state (2026-10-06, rounds 6-13)

Mirror Dungeon floor 3 map (`Exploring Floor 3` / `Repressed Wrath`): the node
layer does not react to taps while the UI layer does (probes: node taps 0.06 -
0.19 frame diff, `?`/`i` open Active Effects, party button opens a bright team
page, `--swipe` pans the map at 5.2). Mean frame brightness has been 11.5 - 11.6
across every round, unchanged from the stalled frame, so no round has sent a
progress input. The entry page reached from the map shows `Enter` disabled. The
reference implementation (LALC) treats this class of state as
human-in-the-loop: it reports "please finish your Dungeon and restart" rather
than guessing.

Unblocking needs one of: the user manually finishing/closing that run in game,
or a client restart - both are outside what this session is allowed to do.
