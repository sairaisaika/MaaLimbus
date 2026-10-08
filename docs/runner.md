# The window runner

`src/maalimbus/runner.py` is the Mirror Dungeon loop itself, with the screen and the
input taken out of it.

It exists because the loop used to live inside `tools/window_step.py`, which is a
command-line tool: it built its own ADB controller, took its own screenshots and sent
its own clicks. Nothing else could drive the loop, and nothing could test it without a
device. The loop is now the library, and the two things it needs are injected:

* a **page** arrives from an *observer* -- a live Maa recognition, or a frame the live
  tools already recorded under `evidence/runtime/**`;
* an **input** leaves through a *device* -- a Maa controller inside an agent custom
  action, the ADB controller the CLI already builds, or an in-memory stand-in in a test.

The decisions did not move: the same `maalimbus.window.plan_step` plans the same single
input per page, the same loop guard, claim guard, unknown-page budget, map tries and
defeat tries bound it, and the same journal events, evidence frames and ledger events
are written. `tools/window_step.py` is now only its command line.

## The device

```python
class Device(Protocol):
    def screencap(self) -> np.ndarray: ...   # BGR, already in the 1920x1080 space
    def click(self, x: int, y: int) -> None: ...
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None: ...
    def key(self, code: int) -> None: ...    # optional; may raise NotImplementedError
```

* `MaaDevice(controller, *, wait=None, target_long_side=1920, deadline=None)` -- wraps
  `context.tasker.controller`. Every call posts its job, waits it out and only then
  returns, so `click()` means the touch landed. The constructor applies
  `set_screenshot_target_long_side(target_long_side)`, which is what pins the frame to
  the recognition space.
* `LocalDevice(controller, *, device=None, tasker=None, deadline=None, wait=None,
  target_long_side=1920)` -- the same mapping for the controller `window_step.py`
  builds, plus `foreground()` for the summary the CLI prints.
* `FakeDevice(frames=(), foreground=None)` -- replays frames and remembers what was
  sent, for tests and dry runs.

## The observer

```python
class Observer(Protocol):
    directory: Path
    def observe(self, *, deadline=None) -> dict: ...   # one page record
```

`MaaObserver(context, directory=None, *, pipeline='WindowMapObserve',
battle_pipeline='WindowBattleObserve')` runs the agent's own recognised pipeline node
and reads back the page it recorded; `FrameObserver(directory, frames=(), *,
index=0, settings=None)` replays archived `frame-*.json` records. A record is the same
JSON the tools already write: `scene`, `size`, `image_sha256`, `ocr`, and whatever the
scene adds (a map header, wave and turn, check odds).

## The loop

```python
MirrorRunner(device, *, settings, locale='en', registry=None, store=None,
             directory=None, journal=None, flow=None, log=None,
             observer=None, roots=None, run_id=None, result=None)

step() -> dict     # one observe -> plan -> act iteration
run(*, steps=300, interval=6.0, round_limit=5, deadline=None) -> dict
```

`step()` reads one page, resolves its scene (the tutorial overlay outranks the label
underneath it), computes the plan, sends the plan's single input through the device,
settles the frame and records the step. It returns `{'page', 'reason', 'target',
'input_sent', 'event', 'stopped', 'done', 'observation', ...}` -- `stopped` names the
condition that ended the window, and `observation` is the record the CLI writes into
`build/window-debug/<label>/frame-*.json`.

`run()` is the outer loop that was in `main()`: it walks `step()` up to `steps` times,
sleeps `interval` between them, keeps the receipt and ledger side effects
(`maalimbus.run_wiring`), and returns the same summary dict the CLI prints.

`settings` is a `maalimbus.runner.Settings` bag, an argparse namespace, or a mapping;
anything left out keeps the CLI's default, so a test only names what it cares about.

## Who uses it

* `tools/window_step.py` builds `LocalDevice`, hands over its `--steps` budget and
  prints the summary; its flags, stdout lines and evidence are unchanged.
* An agent custom action builds `MaaDevice(context.tasker.controller)` and
  `MaaObserver(context, directory)`, and gets the same loop inside the Maa task it
  already owns -- no second controller, no local ADB.
* `tests/test_runner.py` drives the loop over archived frames with a `FakeDevice`.
