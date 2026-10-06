# Who owns the post-battle path: the pipeline or the driver?

Written 2026-10-06 (round 22) from the current tree. Read this before adding
nodes for the reward card, floor gift, shop, next floor or entry return.

## What the pipeline actually reaches

`assets/resource/base/pipeline/mirror.json` (89 nodes) walks the run up to the
battle: mirror entry, difficulty, team, theme packs, deployment, and then
`BattleAutoAssign` / `BattlePlan*` / `BattleObserve` / `BattleStartTurn`, with
`PostBattleObserve` (added in `e974dad`) as the single post-battle hop that
clicks the victory screen and looks for the map.

## What the driver owns

`tools/window_step.py` does not drive the mirror pipeline node by node. It
writes its own three-node pipeline (`PIPELINE` in that file, `prepare()` dumps it
to `pipeline/window.json`):

```python
'WindowMapObserve'    -> DirectHit + Custom 'limbus_map_observe'
'WindowBattleObserve' -> DirectHit + Custom 'limbus_battle_observe'
'WindowDrive'         -> Custom limbus_scene {scene: DRIVE, token: mirror_menu, roi: [...]} + Click
```

Everything else in the per-step loop is Python: it observes a frame, asks
`src/maalimbus/window.py` for a plan (`plan_step`), sends the input itself
through the Maa controller (bounded, with the loop/stall guards), and judges the
result against the plan's `expect`. The plans for `REWARD_CARD`, `GIFT_PICK`,
`GIFT_GET`, `SHOP`, `SHOP_LEAVE`, `EVENT_*`, `MAP` and `NODE_PANEL` all live
there.

## Consequence (the trap to avoid)

There is **no custom action hook that executes a window plan**. Grepping the
agent side for the hooks the pipeline may use yields exactly the 13 names listed
in `docs/p0-pipeline-gap.md`, and none of them runs `plan_step`. So a pipeline
node whose gate is e.g. `limbus_scene {scene: REWARD_CARD}` can only carry a
plain `Click` - which would tap the screen without picking the card and pressing
Confirm, i.e. it would look wired while doing the wrong thing.

## Two honest options

1. **Give the driver the post-battle path** (smallest change, matches what is
   already proven on the device): keep `mirror.json` as the entry-to-battle
   route, and let `window_step.py` continue from `PostBattleObserve` onward,
   since its plans for those pages already exist and are tested offline. The
   pipeline then needs one hand-off node, not six.
2. **Teach the pipeline the whole run**: implement a new custom action in
   `agent/` that runs a `plan_step` (observation in, one bounded input out) and
   use that hook in every post-battle node. This is more work and duplicates the
   driver's guards in a second place.

Recommendation: option 1, and only then decide whether the pipeline should own
the rest. Either way, do not add `Click`-only nodes for pages that need a
decision.

## Unfinished business that does not depend on this choice

* `anchors.json` still lists four pending pages: `identity_filter`,
  `reward_settle`, `run_end_entry_return`, `previous_session_expired` - all four
  need a real run to capture evidence.
* `PostBattleObserve` has never fired on the device: the account has been
  soft-locked on the floor 3 map since round 5 (mean frame brightness 11.5-11.6
  in every round since, zero progress input sent).
