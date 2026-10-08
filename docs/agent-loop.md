# The loop in the agent

`docs/runner.md` is the loop as a library. This is the seam that lets the *packaged app*
drive a whole run: a pipeline node the project interface can point a task at, and the
custom action behind it.

Before this, a whole run only existed as a command line: MXU/PI could load the pipeline
and ask the agent for a page, a team or a proof, but nothing in `assets/` ran the loop.
Now `MirrorLoop` is a node like any other task entry, and the same
`maalimbus.runner.MirrorRunner` runs inside the Maa task the agent already owns -- no
second controller, no local ADB, no separate process.

## The contract

| Pipeline | Agent |
| --- | --- |
| `MirrorLoop` (`custom_action: limbus_mirror_loop`) | `recognition.MirrorLoopAction` |
| `WindowMapObserve` (`limbus_map_observe`) | `recognition.MapObservation` |
| `WindowBattleObserve` (`limbus_battle_observe`) | `recognition.BattleObservation` |
| `MirrorLoopDone` | `DoNothing` |

`MirrorLoop` is `{"recognition": "DirectHit", "action": "Custom", ...}`: it hits at once,
runs the whole run inside the action, and the run's own budget -- not the node's
`timeout` -- is what stops it. A node's `timeout` is the timeout of that node's `next`
list, so `MirrorLoop`'s `400000` only bounds the instant `DirectHit` step into
`MirrorLoopDone`. `on_error` is empty because a run that fails reports through its own
journal instead of the pipeline.

`WindowMapObserve` and `WindowBattleObserve` are the two nodes `MaaObserver` runs. They
are published in `assets/resource/base/pipeline/mirror.json` because a packaged app only
loads what is under `assets/`; the isolated `MapObserve`/`BattleObserve` nodes and the
`MirrorHard` entry chain are untouched. `MirrorLoopDone` is the terminal node the task
ends on, so the task ends the way every other task in this pipeline ends.

## What the action reads

`custom_action_param` is a runner `Settings` mapping, and every name the CLI accepts is
accepted here:

```json
{"directory": "", "steps": 400, "interval": 4.0, "run_store": "config/user-run-ledger.json",
 "team": 5, "rounds": 3, "battle_rounds": 8, "unknown_rounds": 30, "map_tries": 8,
 "claim_tries": 6, "defeat_tries": 2, "defeat_accept": false, "graces": "1,3,5,6,8",
 "grace_budget": 60, "gift_keyword": "bleed", "gift_search": "refuse",
 "gift_plan": "assets/resource/base/gift-plan.json", "observe_only": false,
 "stop_page": null, "budget": 5400}
```

Two of those are the action's own, not the runner's: `directory` (where the evidence
goes) and `budget` (how long the whole run may take, in seconds; the default is one and a
half hours). Anything else the action does not recognise is reported in
`mirror_loop_start.ignored_params` rather than silently kept, so a typo is visible.

The same names can be aimed from the environment, which is how a live run is steered
without editing the pipeline: `MAALIMBUS_LOOP_STEPS=40`, `MAALIMBUS_LOOP_OBSERVE_ONLY=yes`,
`MAALIMBUS_LOOP_TEAM=2`, `MAALIMBUS_LOOP_BUDGET=600`, and so on. The node's own
parameters win over the environment, which wins over the CLI defaults; `steps` defaults
to `400` here (one whole dungeon) where the CLI defaults to the one-shot window `1`.

Unlike the CLI, this action also defaults to the run ledger: `run_store` is
`config/user-run-ledger.json`, so an app run takes its team from the rotation exactly the
way `tools/window_step.py --run-store` does. A ledger the rotation refuses -- another
team list, an impossible rotation -- is journalled as `mirror_loop_store_skipped` and the
run goes on without one, because losing the books is not a reason to abandon a dungeon.

## Where a run writes

Priority: `custom_action_param["directory"]`, then `MAALIMBUS_RUN_DIR`, then
`evidence/runtime/pi-<YYYYmmdd-HHMMSS>` under the application root. A relative path is
resolved against the application root. The directory holds the same evidence the CLI
writes:

* `frame-NNNN.png` + `frame-NNNN.json` -- one page each, from the observation nodes;
* `events.jsonl` -- the run's journal;
* `agent-result.json` -- the summary the runner returns.

`events.jsonl` carries the loop's own records in order:

* `mirror_loop_start` -- the directory, the budget, the deadline, every setting, and the
  parameters that were ignored;
* the loop's page and decision records (`map_observed`, `battle_observed`,
  `window_intent`, `window_page_retry`, `window_claim_guard`, ...);
* `mirror_loop_stopped` -- `reason`, `steps`, `clicks_sent`, `passed`;
* or `mirror_loop_error` -- `error`, `error_type` and the traceback string -- with
  `agent-result.json` holding `reason: mirror_loop_failed`.

The action returns `True` whenever the run reported itself, whatever its reason: the task
is over, and *why* it stopped is in the journal and in `agent-result.json`
(`reason: window_steps_passed`, a stop condition, `loop_deadline_exceeded`, or
`mirror_loop_failed`). It returns `False` only when the run could not report at all.

## Why the observation nodes run through `Context.run_task`

`MaaObserver` runs its node by calling `tasker.post_task(name)` and waiting for the job.
Inside a custom action that cannot be `context.tasker`: the framework's task runner is a
single worker, so a node posted there queues behind the very task that is waiting for it.
The wait then hits its deadline, and the framework's error path stops the running task --
which is this run. `Context.run_task` is the framework's own way to run a pipeline node
from inside a callback: it runs the sub-task synchronously on the calling thread. The
action therefore hands `MaaObserver` an `AgentTasker` proxy, which is both the context
(`.tasker` is itself) and the tasker (`post_task` -> `Context.run_task`). Nothing about
`maalimbus.runner` changes: it still only knows the two-method device and the observer.

Input never leaves any other way. The action builds
`MaaDevice(context.tasker.controller)`, so every click and swipe is a
`post_click`/`post_swipe` job on the controller the PI owns.

## Running it

From MXU/PI: a task whose `entry` is `MirrorLoop`. `MirrorLoop` is deliberately not in
`assets/interface.json` here -- that file is owned elsewhere in this change -- so adding
one task there is all it takes, and no other node changed meaning.

From the command line, on a real device, through the project's own entry point:

```bash
python tools/run_native.py --live --entry MirrorLoop --seconds 3600 \
    --binary <path to the MaaFramework binary the app ships> [--adb <serial>|--address <win32>]
```

`--seconds` is the outer bound -- at most one hour -- and the run also bounds itself with
`budget`, so both stop cleanly. `run_native.py` registers the same hooks, so
`--entry MirrorLoop` runs the loop in this process with no agent socket involved; that is
also the closest thing to the packaged app short of running it. The default
`--entry MirrorHard` chain is unchanged.

## Verifying on a real device

1. Aim the evidence somewhere you can read, and keep the run short enough to watch:

   ```bash
   MAALIMBUS_RUN_DIR=evidence/runtime/loop-check MAALIMBUS_LOOP_BUDGET=600 \
       python tools/run_native.py --live --entry MirrorLoop --seconds 600 --binary <binary>
   ```

2. While it runs, the game should move on its own -- the same clicks the CLI sends, in the
   same order, with the game window focused (the PI's own input method is used, so no
   extra ADB is involved).

3. Afterwards, read the run:

   ```bash
   python -c "import json,pathlib;print([json.loads(l)['event'] for l in pathlib.Path('evidence/runtime/loop-check/events.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()])"
   ```

   Expect `mirror_loop_start` first, the page/decision records between, and
   `mirror_loop_stopped` last -- and no `mirror_loop_error`.

4. Open `evidence/runtime/loop-check/agent-result.json`: `reason`, `steps` (one per input
   sent), `clicks_sent`, `page_before`/`page_after`, and `run_ledger` when the ledger was
   used. A run that stopped because the page went unreadable says so in `reason` instead
   of failing silently.

5. Same run, packaged: launch the app from `dist/MaaLimbus/`, point a task at
   `MirrorLoop`, and confirm a `pi-<stamp>` directory appears under the application root's
   `evidence/runtime/` with the same events. That is the check that the nodes really
   shipped in `assets/`.
