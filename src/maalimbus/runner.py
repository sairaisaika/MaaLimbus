"""The Mirror Dungeon loop, lifted out of ``tools/window_step.py``.

This module exists so that two frontends can drive *the same* loop:

* ``tools/window_step.py`` builds a Maa ADB controller itself and walks one live
  window, exactly as before -- its CLI surface, stdout lines, journal events,
  evidence frames and ledger events are unchanged. Its ``main()`` is now thin:
  it parses the flags, builds the controller, and hands the loop to
  :class:`MirrorRunner`;
* a Maa agent custom action can hand in the controller of the task it is already
  running (``context.tasker.controller``) and drive the same loop without
  building a second controller, without a second ADB device, and without a second
  copy of the plan/guard/DEFEAT/claim logic.

The loop itself is one observe -> plan -> act iteration:

* :meth:`MirrorRunner.step` reads one page through the injected observer, builds
  the same observation record the window has always written into
  ``build/window-debug``, resolves the scene, asks :func:`maalimbus.window.plan_step`
  for the single input it may send (the ``FORBIDDEN_CONTROLS`` refusal, the loop
  guard, ``unknown_rounds``, ``map_tries``, ``claim_tries``, ``defeat_tries`` and
  the retry-reading logic all live on that path), sends it through the injected
  :class:`Device`, and records the same events;
* :meth:`MirrorRunner.run` reproduces the outer loop: the step cap, the interval
  sleep, the same stop conditions, the same receipt/ledger side effects through
  :mod:`maalimbus.run_wiring`, and the same final summary the CLI prints.

Nothing here talks to ADB or to Maa by itself: a page comes from an *observer*
and an input goes to a *device*. That is what makes the loop offline-testable --
:class:`FrameObserver` replays an archived frame into a :class:`FakeDevice`, so a
test drives real archived evidence with no device at all.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

import cv2

from . import session_flow as flows
from .anchors import evaluate
from .event_vision import (best_check_choice, check_box, check_stage, choice_options,
                           gift_hints, odds_scores, preferred_choice)
from .gift_plan import load as load_gift_plan, wanted as wanted_gifts
from .grace_vision import available_starlight, cost_of, plan_purchases, plus_points
from .jobs import wait_job, wait_task
from .map_progress import MapProgress
from .map_vision import NODE_BADGE_TEMPLATE, map_clicks, map_header
from .overlay_vision import carousel_dots, page_turn_arrows
from .reward_vision import (GIFT_COUNTER_BAND, INITIAL_COUNTER_BAND, counter_state,
                            gift_cards, initial_gift_box, keyword_panel_point,
                            select_ready)
from .run_wiring import earned_its_payout, expire, reconcile, settle
from .team_vision import CARD_COUNT, card_states, participants
from .vision import Text, inset_box
from .window import (NODE, SWIPE, WAIT_PAGES, plan_step, resolve_overlay,
                     step_result)

#: repository root: the loop resolves the pipeline, the anchors and the templates
#: relative to it, never relative to the caller's cwd (a Maa agent's cwd is not
#: the repository).
from .runtime_paths import ROOT

#: pages the loop guard never counts: the guide book advances card by card from the
#: same control, and a battle legitimately alternates Win Rate and START.
LOOP_GUARD_EXEMPT = ('TUTORIAL', 'BATTLE_HUD', 'BATTLE_PLANNING')
#: the pages that claiming a finished run walks through, in order and back: the run
#: summary, the reward modal it opens, and the modal's own confirm question. The
#: loop guard below starts over whenever the page changes, so a run that hops
#: between these three never repeats a plan on one page and would never be caught;
#: this family counter is what bounds it.
CLAIM_FAMILY = ('RUN_CLAIM', 'RUN_REWARD_DIALOG', 'RUN_REWARD_CONFIRM')
#: plans the loop guard never counts either: an event's story is tapped through from the
#: same panel for as many taps as it has lines (the user's rule, m10140), and that is
#: progress even though the page name does not move. The step budget bounds them, and a
#: tap that stops changing the frame fails on its own.
LOOP_GUARD_EXEMPT_REASONS = (
    'the_check_outcome_is_tapped_through_until_its_control_lights_up',
    'the_skill_check_story_is_tapped_through_until_it_asks',
    'the_event_result_story_is_tapped_to_reveal_its_continue',
    # The pre-battle team page joins the rotation one identity per tap, so the same plan
    # legitimately runs as many times as the loadout still has empty slots (build/
    # window-run93.json tripped on the third join with eight slots still to fill). The
    # step budget bounds it, and the page moves on to the battle once the team is full.
    'team_card_joins_the_next_unpicked_identity',
    # A skill's detail popup is dismissed by tapping the empty board under it, and that
    # tap is progress even though the page name never moves: live window-20261007-014613
    # is the popup, and the run continues from the battle HUD once it is closed.
    'the_skill_detail_popup_is_dismissed_off_the_board',
    # The victory screen's Confirm can take a tap or two while the result animates in,
    # and the page name does not move until it goes: live window-20261007-015542 shows
    # 130 frames of that one page.
    'victory_confirm_clears_the_result_and_carries_the_rewards',
    # Claiming the run summary plays its own reward animation before the page moves, so
    # the same reason repeats a few times without the page name changing.
    'claiming_is_the_only_forward_input_on_the_run_summary',
    # The reward modal's Claim plays the reward split before it closes, so the same
    # reason and the same page name repeat without meaning the tap was lost.
    'the_reward_modal_is_claimed_and_never_given_up',
    # A story cutscene is skipped once per line and can run several frames long, so the
    # same plan legitimately repeats with the page name standing still: live build/
    # window-run-continue-6.json skipped it three times on the way into an event's check
    # page, and the third skip that actually revealed EVENT_CHECK_READY was the one the
    # guard called a repeat and stopped the run on. The step budget bounds it.
    'the_cutscene_is_skipped_to_resume_the_run',
)

#: the observation pipeline ``prepare()`` writes; the window drives these nodes and
#: an agent action registers the matching custom recognitions/actions.
PIPELINE = {
    'WindowMapObserve': {
        'recognition': 'DirectHit', 'action': 'Custom',
        'custom_action': 'limbus_map_observe',
        'max_hit': 1, 'next': [], 'on_error': [],
    },
    'WindowBattleObserve': {
        'recognition': 'DirectHit', 'action': 'Custom',
        'custom_action': 'limbus_battle_observe',
        'max_hit': 1, 'next': [], 'on_error': [],
    },
    # Mirror menu card: the recognition owns the click box, so the window never
    # invents a coordinate for the dungeon entry.
    'WindowDrive': {
        'recognition': 'Custom', 'custom_recognition': 'limbus_scene',
        'custom_recognition_param': {'scene': 'DRIVE', 'token': 'mirror_menu',
                                    'roi': [.23, .25, .46, .55]},
        'action': 'Click', 'target': True, 'post_delay': 1000, 'max_hit': 1,
        'next': [], 'on_error': [],
    },
}

#: the pages whose fight readout (wave/turn) has to move for the step to count.
BATTLE_PAGES = ('BATTLE_HUD', 'BATTLE_PLANNING')


def _defaults():
    """The window's argparse defaults, in one place.

    The CLI builds its namespace from this mapping and its help text from the
    parser below, so a default is edited once rather than twice.
    """
    return {
        'steps': 1, 'rounds': 3, 'unknown_rounds': 30, 'battle_rounds': 8,
        'interval': 4.0, 'map_tries': 8, 'page_tries': 3, 'team': 5,
        'gift_keyword': 'bleed', 'gift_plan': 'assets/resource/base/gift-plan.json',
        'gift_search': 'refuse', 'loop_guard': 3, 'claim_tries': 6,
        'observe_only': False, 'stop_page': None, 'grace_budget': 60,
        'observe_page': False, 'defeat_tries': 2, 'defeat_accept': False,
        'graces': '1,3,5,6,8', 'map_points': '', 'flow': None, 'flow_timeout': None,
        'after_flow': False, 'swipe': None, 'click_box': None, 'label': 'one_shot_click',
        'run_store': None, 'report': None, 'address': '', 'binary': None, 'adb': None,
        'input_method': None, 'authorize': '',
    }


class Settings:
    """A settings bag: named attributes, an argparse namespace or a mapping.

    Anything the caller leaves out keeps the CLI's default, so a fake-device test
    only has to name what it cares about.
    """

    def __init__(self, source=None):
        object.__setattr__(self, '_values', dict(_defaults()))
        if source is not None:
            self._values.update(_overrides(source))

    def __getattr__(self, name):
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name, value):
        self._values[name] = value

    def __getitem__(self, name):
        return self._values[name]

    def get(self, name, default=None):
        return self._values.get(name, default)

    def as_dict(self):
        return dict(self._values)


def _overrides(source):
    if isinstance(source, Settings):
        return source.as_dict()
    if hasattr(source, '_values'):
        return dict(source._values)
    if hasattr(source, '__dict__') and not isinstance(source, (dict, list, tuple)):
        return {key: value for key, value in vars(source).items()
                if not key.startswith('_') and value is not None}
    return dict(source)


def settings(source=None):
    """Normalize settings into the object the runner reads (idempotent)."""
    return source if isinstance(source, Settings) else Settings(source)


# --------------------------------------------------------------------------- the gate


AUTHORIZATION = ROOT / 'build/map-probe-authorization.json'
REGISTRY = ROOT / 'assets/resource/base/anchors.json'
PIPELINE_DIR = ROOT / 'build/window-debug'


def prepare() -> Path:
    """Write the observation pipeline and return the directory it lives in."""
    (PIPELINE_DIR / 'pipeline').mkdir(parents=True, exist_ok=True)
    (PIPELINE_DIR / 'pipeline/window.json').write_text(
        json.dumps(PIPELINE, indent=2) + '\n', encoding='utf-8')
    return PIPELINE_DIR


def authorized(nonce: str) -> bool:
    """Whether the live-input gate grants this nonce."""
    if not AUTHORIZATION.is_file():
        return False
    data = json.loads(AUTHORIZATION.read_text(encoding='utf-8'))
    return (data.get('live_input_authorized') is True and bool(data.get('nonce'))
            and data['nonce'] == nonce)


# --------------------------------------------------------------------------- device


@runtime_checkable
class Device(Protocol):
    """One screen and one touch surface, whatever is behind them.

    ``screencap`` returns a BGR image already in the 1920x1080 recognition space;
    ``click``/``swipe`` take that same space. The one rule the loop relies on is
    that a sent input has *landed* by the time the call returns -- both Maa and the
    ADB path wait the job out before returning.
    """

    def screencap(self):
        """The fresh frame, BGR, in the 1920x1080 recognition space."""

    def click(self, x: int, y: int) -> None:
        """Tap one point."""

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        """Drag one point to another over ``duration_ms``."""

    def key(self, code: int) -> None:
        """Press one key by Maa keycode; optional, may raise NotImplementedError."""


class MaaDevice:
    """A :class:`Device` over a MaaFramework controller.

    ``controller`` is ``context.tasker.controller`` in an agent custom action, so
    this never builds a controller of its own and never needs one: the loop's input
    goes out through the task the agent already owns. Every call posts its job,
    waits it out under a deadline and only then returns, which is what makes
    ``click()`` mean "the touch landed" rather than "the touch was queued".
    """

    def __init__(self, controller, *, wait=None, target_long_side=1920, deadline=None):
        self.controller = controller
        self.wait = wait
        self.deadline = deadline
        self.target_long_side = target_long_side
        if target_long_side:
            controller.set_screenshot_target_long_side(int(target_long_side))

    def _limit(self, timeout):
        end = time.monotonic() + timeout
        if self.deadline is not None:
            end = min(end, self.deadline)
        return end

    def _wait(self, job, timeout=10):
        limit = self._limit(timeout)
        if self.wait is not None:
            return self.wait(job, timeout=timeout, deadline=limit)
        return wait_job(job, timeout=timeout, deadline=limit)

    def screencap(self):
        """Post a screencap, wait it out and return the cached BGR frame."""
        self._wait(self.controller.post_screencap())
        return self.controller.cached_image

    def click(self, x, y):
        self._wait(self.controller.post_click(int(x), int(y)))

    def swipe(self, x1, y1, x2, y2, duration_ms):
        self._wait(self.controller.post_swipe(int(x1), int(y1), int(x2), int(y2),
                                              int(duration_ms)), timeout=15)

    def key(self, code):
        post = getattr(self.controller, 'post_key', None)
        if post is None:
            raise NotImplementedError('this controller has no key input')
        self._wait(post(int(code)))


class LocalDevice:
    """A :class:`Device` over the ADB controller the CLI already built.

    ``tools/window_step.py`` uses this, so its input goes through the same
    ``post_click``/``post_swipe`` calls it always has. It also answers
    ``foreground()``, which the window's summary reports and a Maa task's
    controller cannot.
    """

    def __init__(self, controller, *, device=None, tasker=None, deadline=None,
                 wait=None, target_long_side=1920):
        self.controller = controller
        self.device = device
        self.tasker = tasker
        self.wait = wait
        self.deadline = deadline
        self.target_long_side = target_long_side
        if target_long_side:
            controller.set_screenshot_target_long_side(int(target_long_side))

    def _limit(self, timeout):
        end = time.monotonic() + timeout
        if self.deadline is not None:
            end = min(end, self.deadline)
        return end

    def _wait(self, job, timeout=10):
        limit = self._limit(timeout)
        if self.wait is not None:
            return self.wait(job, timeout=timeout, deadline=limit)
        return wait_job(job, timeout=timeout, deadline=limit)

    def screencap(self):
        self._wait(self.controller.post_screencap())
        return self.controller.cached_image

    def click(self, x, y):
        self._wait(self.controller.post_click(int(x), int(y)))

    def swipe(self, x1, y1, x2, y2, duration_ms):
        self._wait(self.controller.post_swipe(int(x1), int(y1), int(x2), int(y2),
                                              int(duration_ms)), timeout=15)

    def key(self, code):
        post = getattr(self.controller, 'post_key', None)
        if post is None:
            raise NotImplementedError('this controller has no key input')
        self._wait(post(int(code)))

    def foreground(self):
        """The foreground window of the ADB device, or ``None`` when unknown."""
        if self.device is None:
            return None
        from .adb_device import foreground_of
        return foreground_of(self.device)


def local_device(controller, device=None, tasker=None, *, deadline=None, wait=None,
                 target_long_side=1920):
    """Build the ADB-side device the window has always driven."""
    return LocalDevice(controller, device=device, tasker=tasker, deadline=deadline,
                       wait=wait, target_long_side=target_long_side)


class FakeDevice:
    """A :class:`Device` for tests: replays frames and remembers what was sent."""

    def __init__(self, frames=(), foreground=None):
        self.frames = list(frames)
        self.clicks = []
        self.swipes = []
        self.keys = []
        self._foreground = foreground

    def push(self, frame):
        self.frames.append(frame)

    def screencap(self):
        return self.frames.pop(0) if self.frames else None

    def click(self, x, y):
        self.clicks.append((int(x), int(y)))

    def swipe(self, x1, y1, x2, y2, duration_ms):
        self.swipes.append((int(x1), int(y1), int(x2), int(y2), int(duration_ms)))

    def key(self, code):
        self.keys.append(int(code))

    def foreground(self):
        return self._foreground


# --------------------------------------------------------------------------- frames


def events(directory, name):
    """Every journal event of one kind, oldest first."""
    path = Path(directory) / 'events.jsonl'
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get('event') == name:
            records.append(record)
    return records


def latest_frame(directory):
    """The newest readable frame image and its name, or ``(None, None)``."""
    for path in sorted(Path(directory).glob('frame-*.png'), reverse=True):
        image = cv2.imread(str(path))
        if image is not None:
            return image, path.name
    return None, None


def frame_sha(directory):
    """The sha256 the journal recorded for the newest stored frame.

    A frame is only stored when the pixels change, so the newest frame's hash is
    the identity of the screen just observed.
    """
    for path in sorted(Path(directory).glob('frame-*.json'), reverse=True):
        try:
            sha = json.loads(path.read_text(encoding='utf-8')).get('image_sha256')
        except (OSError, ValueError):
            continue
        if sha:
            return sha
    return None


def frame_file(directory):
    """The newest stored frame's JSON, which is the proof a ledger event names.

    ``RunStore.record`` hashes the file it is handed, so the ledger's proof is the
    same frame the window just read rather than a page name taken on trust.
    """
    for path in sorted(Path(directory).glob('frame-*.json'), reverse=True):
        try:
            if json.loads(path.read_text(encoding='utf-8')).get('image_sha256'):
                return path
        except (OSError, ValueError):
            continue
    return None


def frame_details(directory):
    """The newest stored frame's ``ocr`` tokens and ``size``, or ``None``.

    The analyze event carries only semantic fields (scene, floor, pack, boxes), so
    the token list and frame size that the guide-book and team readers need come
    from the frame record the journal writes next to the image.
    """
    for path in sorted(Path(directory).glob('frame-*.json'), reverse=True):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if data.get('ocr') or data.get('size'):
            return data
    return None


def _next_frame_name(directory):
    index = len(list(Path(directory).glob('frame-*.png'))) + 1
    while (Path(directory) / ('frame-%04d.json' % index)).exists():
        index += 1
    return 'frame-%04d' % index


def store_frame(directory, record, image=None, *, name=None):
    """Persist one frame record (and its pixels) into ``directory``.

    ``record`` is the same shape the journal writes; ``image`` is the BGR frame it
    came from. This is how :class:`FrameObserver` turns an archived frame or an
    in-memory page into a real ``frame-NNNN{.json,.png}`` pair, so every helper
    that resolves the observation directory -- map candidates, page-turn arrows,
    the ledger's evidence proof -- reads exactly the frame the record came from.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = name or (record.get('frame') if isinstance(record, dict) else None)
    if not name or (directory / (str(name) + '.json')).exists():
        name = _next_frame_name(directory)
    record = dict(record)
    record.pop('image', None)
    record.pop('frame', None)
    if image is not None:
        cv2.imwrite(str(directory / (str(name) + '.png')), image)
        record['size'] = record.get('size') or [image.shape[1], image.shape[0]]
    (directory / (str(name) + '.json')).write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return record


def load_frame(path, directory, *, name=None):
    """Copy an archived ``frame-NNNN.png``/``.json`` pair into ``directory``."""
    path = Path(path)
    record = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    image = cv2.imread(str(path.with_suffix('.png')))
    return store_frame(directory, record, image, name=name)


def screencap_record(device, directory, *, name=None, scene='UNKNOWN'):
    """Read one screenshot through the device and store it as a frame record.

    The pixels are all a bare :class:`Device` can prove: the record carries the
    image hash, the frame name and the size. Recognition fills the rest in when
    the observer has it.
    """
    image = device.screencap()
    if image is None:
        raise RuntimeError('the device returned no screenshot')
    digest = hashlib.sha256(image.tobytes()).hexdigest()
    return store_frame(directory, {'scene': scene, 'image_sha256': digest,
                                   'size': [image.shape[1], image.shape[0]]},
                       image, name=name)


# --------------------------------------------------------------------------- observer


@runtime_checkable
class Observer(Protocol):
    """Where a page comes from.

    A page is the record the window's journal has always written: ``scene``,
    ``size``, ``floor``/``pack``/``wave``/``turn``, ``start_box``,
    ``auto_assign_buttons`` and the OCR tokens. The loop never reads the game
    itself, so a replayed archived frame and a live Maa recognition are
    interchangeable.
    """

    directory: Path

    def observe(self, *, deadline=None) -> dict:
        """Read one fresh page."""


class FrameObserver:
    """A page from an already-recorded frame: the offline half of the loop.

    ``frames`` may be frame records (the JSON the journal writes), ``frame-NNNN``
    names, or ``.png``/``.json`` paths; each one is copied into ``directory``
    under its own or the next free frame name, so a test replays archived evidence
    and gets the same frames on disk that a live window would have written.
    """

    def __init__(self, directory, frames=(), *, index=0, settings=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.frames = list(frames)
        self.index = index
        self.settings = settings
        self.records = []

    def observe(self, *, deadline=None):
        if self.index >= len(self.frames):
            raise IndexError('FrameObserver has no frame left to observe')
        frame = self.frames[self.index]
        self.index += 1
        if isinstance(frame, (str, Path)):
            frame = load_frame(Path(frame), self.directory)
        else:
            frame = store_frame(self.directory, frame,
                                frame.get('image') if isinstance(frame, dict) else None)
        self.records.append(frame)
        return frame


class MaaObserver:
    """A page from Maa pipeline nodes, driven through an injected context.

    ``context`` is anything with the three things a page needs: ``tasker`` (the
    tasker whose pipeline nodes are run), ``run`` (a callable that runs one node by
    name), and ``journal`` (an object with ``record(name, **fields)`` -- the
    window's journal). ``tools/window_step.py`` passes its own; an agent custom
    action passes the ones its context already has.
    """

    def __init__(self, context, directory=None, *, pipeline='WindowMapObserve',
                 battle_pipeline='WindowBattleObserve'):
        self.context = context
        self.directory = Path(directory if directory is not None
                              else getattr(context, 'directory', '.'))
        self.pipeline = pipeline
        self.battle_pipeline = battle_pipeline

    @property
    def tasker(self):
        """The tasker whose pipeline nodes are run (a runner or a context has one)."""
        return getattr(self.context, 'tasker', None)

    def observe(self, *, deadline=None):
        run_node(self.tasker, self.pipeline, deadline)
        record = events(self.directory, 'map_observed')[-1]
        if record.get('scene') in BATTLE_PAGES:
            run_node(self.tasker, self.battle_pipeline, deadline)
            record = events(self.directory, 'battle_observed')[-1]
        return record


def observe(observer, deadline=None):
    """Read the live page once and return its journal record.

    The analyze event itself carries no frame hash, tokens or size, so they are
    attached here: the repeated-card guard, the "did the click move the screen"
    check, the guide-book carousel and the pre-battle team reader all need them.
    """
    record = observer.observe(deadline=deadline)
    if not record.get('image_sha256'):
        record['image_sha256'] = frame_sha(observer.directory)
    details = frame_details(observer.directory)
    if details:
        if not record.get('size'):
            record['size'] = details.get('size')
        if not record.get('ocr'):
            record['ocr'] = details.get('ocr')
    return record


# --------------------------------------------------------------------------- readings


def controls_by_id(registry: dict) -> dict:
    """Anchor name -> proven pixel box, from the anchors registry."""
    controls = {}
    for page in registry.get('pages', []):
        for control in page.get('controls', []):
            box = (control.get('verified_on') or {}).get('box')
            if box is not None:
                controls[control['id']] = list(box)
    return controls


def node_badge_template():
    """The crescent emblem every map node hangs under its hexagon, or None."""
    if not hasattr(node_badge_template, 'cache'):
        path = ROOT / 'assets/resource/base' / NODE_BADGE_TEMPLATE
        node_badge_template.cache = cv2.imread(str(path)) if path.exists() else None
    return node_badge_template.cache


def candidates_of(directory, record):
    """Ordered click boxes for a MAP page, the step the game marks first.

    Which nodes the run may step to depends on the paths drawn under the dots, and
    that connectivity is not readable from a frame, so the list is ordered and never
    filtered: the window tries them in turn and stops at the first that really opens
    the panel, and a click on an unreachable node is a harmless no-op. The order comes
    from map_vision.map_clicks: the desaturated-bright glyph the game uses to mark the
    step it will accept, then the crescent-badge nodes away from the player.
    """
    if record['scene'] != 'MAP':
        return None, None
    image, name = latest_frame(directory)
    if image is None:
        return None, None
    clicks = map_clicks(image, template=node_badge_template())
    return name, [list(item['box']) for item in clicks]


def check_of(directory, record, *, page=None):
    """The identity slot a skill check should be rolled by, or ``None``.

    The check page prints an odds caption over every identity card, and OCR merges the
    whole row into one token, so the captions are matched as templates instead (see
    maalimbus.event_vision). The best trusted slot's card box is what the plan clicks.

    ``page`` is the scene the run loop resolved, and it is what gates this reading: a
    check whose question the recogniser has not learned yet is still named EVENT_CHECK
    by resolve_scene's Commence fallback while its raw scene stays UNKNOWN.
    """
    if (page or record['scene']) != 'EVENT_CHECK':
        return None
    stage = check_stage(record.get('ocr') or ())
    if stage:
        return {'stage': stage}
    image, name = latest_frame(directory)
    if image is None:
        return None
    scores = odds_scores(image)
    slot = best_check_choice(scores)
    if not slot:
        return None
    height, width = image.shape[:2]
    chosen = next((item for item in scores if item['index'] == slot), {})
    return {'slot': slot, 'tier': chosen.get('tier'),
            'box': check_box(slot, (width, height)), 'frame': name,
            'odds': scores}


def overlay_hit(registry, directory, record):
    """True when the guide book is on screen.

    Only identities that exist *without* the book count here: the book's carousel
    dots and the template of its own continue control. The page-turn triangle is
    deliberately not an identity -- it shares its right-hand band with other UI, and
    in live run window-20261006-034009 that turned twelve team page observations
    into "tutorial" clicks on the Details button.
    """
    image, name = latest_frame(directory)
    if image is None:
        return None
    size = tuple(record.get('size') or ())
    if len(size) == 2 and record.get('ocr'):
        records = [Text(item['text'], tuple(item['box']), item['score'])
                   for item in record['ocr']]
        if carousel_dots(records, size):
            return True
    arrows = page_turn_arrows(image)
    if not arrows.get('previous') and not arrows.get('next'):
        return False
    height, width = image.shape[:2]
    observation = {'size': [width, height],
                   'image_sha256': record.get('image_sha256')}
    report = evaluate(registry, observation, page='tutorial',
                      image_path=str(directory / name),
                      template_root=ROOT / 'assets/resource/base')
    for page in report['pages']:
        for anchor in list(page.get('identity') or []) + list(page.get('controls') or []):
            if anchor.get('id') == 'tutorial.next_glyph':
                return anchor.get('hit')
    return None


def arrows_of(directory):
    """The guide overlay's live page-turn triangles, or ``None`` without a frame."""
    image, _name = latest_frame(directory)
    if image is None:
        return None
    return page_turn_arrows(image)


def resolve_scene(registry, directory, record):
    """Page identity, with the tutorial overlay taking precedence while it is up."""
    scene = record['scene']
    # The skill check prints its question several ways, and a wording the locale has
    # not learned yet would leave the rolled page UNKNOWN while the run waited out its
    # clock (build/window-run84.json). Its Commence button exists nowhere else, so the
    # button names the page whatever the question says.
    if scene == 'UNKNOWN' and check_stage(record.get('ocr') or ()) == 'commence':
        scene = 'EVENT_CHECK'
    return resolve_overlay(scene,
                           overlay_hit=bool(overlay_hit(registry, directory, record)))


def team_state(record, controls):
    """The pre-battle page's per-card participation badges, or ``None``.

    The page opens with 0/12 picked and a dark Battle! button, so the driver has to
    hand the planner what is already in the team rather than clicking blind.
    """
    size = tuple(record.get('size') or ())
    if len(size) != 2 or not record.get('ocr'):
        return None
    records = [Text(item['text'], tuple(item['box']), item['score'])
               for item in record['ocr']]
    boxes = [controls.get('pre_battle.card_%02d' % index)
             for index in range(1, CARD_COUNT + 1)]
    if not any(boxes):
        return None
    return {'states': card_states(records, boxes, size),
            'participants': participants(records, size)}


def reward_state(record):
    """The encounter reward page's pick counter, as ``{'chosen': n, 'required': m}``."""
    return counter_state(record)


def unselected_reward_successor(record):
    """Independent encounter-reward anchors, not a page label alone."""
    texts = [r['text'].strip() for r in record.get('ocr', []) if r['score'] >= .9]
    count = reward_state(record)
    if (count == {'chosen': 0, 'required': 1}
            and 'Select Encounter Reward Card' in texts
            and 'Selectable' in texts
            and any('Confirm' in t for t in texts)
            and any('Cancel' in t for t in texts)):
        return dict(count=count, title='Select Encounter Reward Card')
    return None


def gift_state(record, *, image=None, select_box=None, picks=0):
    """The floor gift page's pick state, as ``{'chosen': n, 'required': m, 'ready': b}``.

    ``chosen`` falls back to the driver's own count of the cards it has already
    clicked on this page, and ``ready`` comes from the button's pixels, which both
    live variants of the page share.
    """
    state = counter_state(record, band=GIFT_COUNTER_BAND) or {}
    chosen = state.get('chosen')
    return {'chosen': int(picks if chosen is None else chosen),
            'required': state.get('required'),
            'ready': select_ready(image, select_box) if select_box else None}


def flow_token(record, step):
    """The token a named-flow step is waiting for on the page just read, or ``None``."""
    return flows.token_of(record.get('ocr') or [],
                          record.get('size') or (1920, 1080), step)


def run_node(tasker, name, deadline):
    """Run one pipeline node and wait it out inside the window's deadline."""
    job = tasker.post_task(name)
    try:
        return wait_task(tasker, job, deadline=deadline)
    except RuntimeError as error:
        if not job.done:
            wait_job(tasker.post_stop(), timeout=5)
        return {'task_succeeded': False, 'stop_confirmed': job.done, 'error': str(error)}


def record_ledger_event(store, run_id, directory, page, plan, floor_now, journal=None):
    """Record every ledger event this page settles, each proved by its own frame.

    The rule and the loop live in ``maalimbus.run_wiring.settle`` so they can be tested
    without a device; this wrapper hands them the frame the event must name and journals
    what was recorded (or refused).
    """
    proof = frame_file(directory)
    if proof is None:
        return []

    def note(event):
        if journal is not None:
            journal.record('run_ledger_event', kind=event.kind, floor=event.floor,
                           evidence=str(proof))

    def refuse(event, error):
        if journal is not None:
            journal.record('run_ledger_refused', kind=event.kind, floor=event.floor,
                           evidence=str(proof), reason=str(error))

    return settle(store, page=page, reason=plan.get('reason'),
                  floor=floor_now if page == 'MAP' else None, proof=proof,
                  on_event=note, on_refusal=refuse)


# --------------------------------------------------------------------------- flows


def run_flow(tasker, controller, journal, directory, deadline, steps, *, observer=None,
             registry=None, observe_only=False, interval=4.0, rounds=3):
    """Walk a named flow and return one record per step.

    Each step waits for its own token, clicks inside that token's box, and stops the
    whole flow the moment the page does not answer. One step is one input: the flow
    never guesses a coordinate for a control it has not recognised, and never sends a
    second input to a page that did not move.
    """
    if observer is None:
        observer = MaaObserver(tasker, directory)
    records = []
    for step in steps:
        entry = {'step': step.id, 'kind': step.kind, 'pattern': step.pattern,
                 'roi': None if step.roi is None else list(step.roi),
                 'optional': bool(step.optional), 'repeat': step.repeat, 'clicks': 0,
                 'note': step.note}
        if step.kind == 'start_app':
            if observe_only:
                entry.update(passed=False, reason='observe_only')
                records.append(entry)
                continue
            wait_job(controller.post_start_app(flows.LAUNCH_INTENT), timeout=30,
                     deadline=deadline)
            journal.record('flow_start_app', intent=flows.LAUNCH_INTENT)
            entry.update(passed=True, reason='start_app_sent')
            records.append(entry)
            time.sleep(min(interval, 3.0))
            continue
        limit = time.monotonic() + step.timeout_s
        record, token = None, None
        while True:
            record = observe(observer, deadline)
            token = flow_token(record, step)
            if token is not None or step.optional or time.monotonic() >= limit:
                break
            time.sleep(min(interval, 2.0))
        entry.update(page=record.get('scene'), observation=record, token=token)
        if token is None:
            entry.update(passed=bool(step.optional),
                         reason=('flow_token_absent_skipped' if step.optional
                                 else 'flow_token_not_seen'))
            records.append(entry)
            if not step.optional:
                return records
            continue
        if step.kind == 'wait':
            entry.update(passed=True, reason='flow_token_seen')
            records.append(entry)
            continue
        if observe_only:
            entry.update(passed=False, reason='observe_only')
            records.append(entry)
            continue
        sent, changed = 0, False
        for _index in range(max(1, step.repeat)):
            before_sha = record.get('image_sha256')
            x, y, w, h = flows.center(token['box'])
            point = (random.randint(x, x + max(1, w - 1)),
                     random.randint(y, y + max(1, h - 1)))
            delay = random.randint(350, 750)
            journal.record('flow_intent', step=step.id, note=step.note,
                           pattern=step.pattern, target=list(token['box']),
                           point=list(point), delay_ms=delay)
            wait_job(controller.post_click(*point), timeout=10, deadline=deadline)
            sent += 1
            time.sleep(delay / 1000)
            settled = record
            for round_index in range(max(1, rounds)):
                if round_index:
                    time.sleep(interval)
                settled = observe(observer, deadline)
                if settled.get('image_sha256') not in (None, before_sha):
                    break
            changed = settled.get('image_sha256') not in (None, before_sha)
            record = settled
            token = flow_token(settled, step)
            if token is None:
                break
        entry.update(clicks=sent, changed=bool(changed), token_after=token,
                     page_after=record.get('scene'), settled=record,
                     passed=bool(changed or token is None),
                     reason='flow_step_clicked' if changed else 'flow_step_unchanged')
        records.append(entry)
        if not entry['passed']:
            return records
    return records


class _Context:
    """Kept for callers that still hand a bare tasker and journal to a helper."""

    def __init__(self, tasker, journal=None, directory=None):
        self.tasker = tasker
        self.journal = journal
        self.directory = directory


# --------------------------------------------------------------------------- runner


class MirrorRunner:
    """One bounded window: walk the live dungeon loop and record every page it meets.

    The runner owns the *decisions*; it owns neither the screen nor the input. A
    page arrives from ``observer`` (a live Maa recognition or a replayed archived
    frame) and every input leaves through ``device`` (a Maa controller or an
    in-memory stand-in), which is what lets the same loop run live, run inside an
    agent custom action, and run in a test with no device at all.
    """

    def __init__(self, device, *, settings, locale='en', registry=None, store=None,
                 directory=None, journal=None, flow=None, log=None, observer=None,
                 roots=None, run_id=None, result=None):
        self.device = device
        self.settings = settings if isinstance(settings, Settings) else Settings(settings)
        self.locale = locale
        self.registry = registry if registry is not None else _load_registry()
        self.store = store
        self.run_id = run_id
        self.directory = Path(directory) if directory is not None else Path(os.getcwd())
        self.directory.mkdir(parents=True, exist_ok=True)
        self.journal = journal
        self.flow = flow
        self.log = log
        self.roots = roots if roots is not None else _roots()
        self.controls = controls_by_id(self.registry)
        self.observer = (observer if observer is not None
                         else MaaObserver(self, self.directory))
        if getattr(self.observer, 'directory', None) is None:
            self.observer.directory = self.directory
        self.deadline = None
        self.last_event = None
        # A caller that already owns a result dict (the CLI does) hands it in: the
        # summary then fills that same dict, so the file it writes keeps the caller's
        # own key order and any extra evidence keys it had put there.
        self.result = result if result is not None else {}
        self.artifacts = {'steps': [], 'flow_steps': [], 'clicks_sent': 0,
                          'verified_clear': False, 'flow': None}
        if result is not None:
            self.artifacts['steps'] = result.setdefault('steps', [])
            self.artifacts['clicks_sent'] = int(result.get('clicks_sent') or 0)
        self.state = _fresh_state(self.settings, self.store)
        from .grace_transaction import GraceTransaction
        self.grace_transaction = (GraceTransaction(self.store.path.parent/'user-grace-transaction.json')
                                  if self.store is not None else None)
        from .initial_transaction import InitialTransaction
        self.initial_transaction=(InitialTransaction(self.store.path.parent/'user-initial-transaction.json')
                                  if self.store is not None else None)
        from .deployment_transaction import DeploymentTransaction
        self.deployment_transaction=(DeploymentTransaction(self.store.path.parent/'user-deployment-transaction.json')
                                     if self.store is not None else None)
        from .theme_transaction import ThemeTransaction
        self.theme_transaction=(ThemeTransaction(self.store.path.parent/'user-theme-transaction.json')
                                if self.store is not None else None)
        from .floor_gift_transaction import FloorGiftTransaction
        self.floor_gift_transaction=(FloorGiftTransaction(self.store.path.parent/'user-floor-gift-transaction.json')
                                     if self.store is not None else None)
        self.floor_gift_catalog=None

    # -- small services the observer/flow may use --------------------------
    @property
    def tasker(self):
        return getattr(self.device, 'tasker', None)

    @property
    def controller(self):
        return getattr(self.device, 'controller', None)

    def configure(self, *, deadline=None, settings=None, flow=None, run_id=None,
                  store=None):
        """Set the per-run values (deadline, settings, flow names) before ``run``."""
        if deadline is not None:
            self.deadline = deadline
        if settings is not None:
            self.settings = settings if isinstance(settings, Settings) else Settings(settings)
            self.state = _fresh_state(self.settings, self.store)
        if flow is not None:
            self.flow = flow
            self.artifacts['flow'] = ','.join(flow) if not isinstance(flow, str) else flow
        if run_id is not None:
            self.run_id = run_id
        if store is not None:
            self.store = store

    def note(self, name, **fields):
        """Journal one event, when a journal is attached."""
        self.last_event = name
        if self.journal is not None:
            self.journal.record(name, **fields)

    def _observe(self, deadline=None):
        """One page, from the injected observer, with the journal details attached."""
        return observe(self.observer, self.deadline if deadline is None else deadline)

    def _flow(self, deadline, steps, observe_only):
        """Walk the named session flow, then report its records.

        Each step waits for its own token, clicks inside that token's box, and stops
        the whole flow the moment the page does not answer. One step is one input:
        the flow never guesses a coordinate for a control it has not recognised, and
        never sends a second input to a page that did not move.
        """
        if self.controller is None:
            raise RuntimeError('a named flow needs a controller')
        return run_flow(self.tasker, self.controller, self.journal, self.directory,
                        deadline, steps, observer=self.observer,
                        registry=self.registry,
                        observe_only=observe_only or self.settings.observe_only,
                        interval=self.settings.interval, rounds=self.settings.rounds)

    # -- the loop ----------------------------------------------------------
    def step(self):
        """One observe -> plan -> act iteration; returns its record.

        The returned dict carries the page it read, the reason the plan gives, the
        target box it aimed at (or ``None``), whether input was sent, the journal
        event that decision produced, the stop reason when this step ended the
        window, whether the window is done, and the observation record itself --
        the same JSON the CLI writes into ``build/window-debug/<label>/frame-*.json``.
        """
        settings = self.settings
        state = self.state
        directory = self.directory
        record = self._observe()
        page = resolve_scene(self.registry, directory, record)
        # The map floor numeral blinks. A missing digit is not a failed drag:
        # reread the current page within the existing bounded settle budget.
        if page=='MAP' and self.theme_transaction is not None and self.theme_transaction.data and self.theme_transaction.data.get('pending'):
            for attempt in range(max(1,settings.rounds)-1):
                texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
                header=map_header(texts,record.get('size') or (1920,1080))
                if not header or header.floor is not None:break
                self.note('map_floor_read_retry',attempt=attempt+1,input_sent=False)
                time.sleep(settings.interval)
                record=self._observe()
                page=resolve_scene(self.registry,directory,record)
                if page!='MAP':break
        frame, candidates = candidates_of(directory, record)
        if self.store is not None and not settings.observe_only:
            active=self.store.data.get('active') or {}
            if active.get('phase')=='entry_pending' and page in ('STAR_GRACES','INITIAL_GIFTS','THEME_PACKS','MAP'):
                self.store.entry_observed(self.run_id,page,frame_file(directory))
            if active.get('phase')=='entry_pending' and page=='DUNGEON_TEAM':
                stopped=self._record(page,record,frame,candidates,None,'entry_confirmation_pending_no_retry')
                return self._result(page,None,False,stopped,done=True)
        if settings.stop_page and page==settings.stop_page:
            stopped=self._record(page,record,frame,candidates,None,'stop_page_reached')
            return self._result(page,None,False,stopped,done=True)
        if page=='EVENT_RESULT':
            from .event_vision import event_result_content
            signature=event_result_content(record.get('ocr'),record.get('size') or (1920,1080))
            state['event_unchanged']=(state.get('event_unchanged',0)+1
                                      if signature and signature==state.get('event_signature') else 0)
            state['event_signature']=signature
            if state['event_unchanged']>=3:
                stopped=self._record(page,record,frame,candidates,None,'event_result_semantic_progress_stalled')
                return self._result(page,None,False,stopped,done=True)
        else:
            state['event_unchanged']=0;state['event_signature']=None
        if page in ('BATTLE_HUD','DEPLOYMENT') and self.deployment_transaction is not None:
            d=self.deployment_transaction.data
            if d and d.get('submit_pending') and d['scope']==self.run_id:
                from .storage import write_json
                d.update(submitted=True,submit_pending=False,battle_proof=str(frame_file(directory)))
                write_json(self.deployment_transaction.path,d)
        if page in ('RUN_REWARD_DIALOG','RUN_REWARD_CONFIRM','RUN_REWARD_BONUS'):
            # These controls can commit module costs. A victory flag is not a
            # spending authorization; retain the cost screen for budget review.
            from .storage import read_json
            policy_path=(self.store.path.parent if self.store is not None else ROOT/'config')/'user-mirror-settings.json'
            policy=read_json(policy_path) if policy_path.exists() else {}
            maximum=policy.get('max_reward_modules')
            reason=('reward_module_budget_pending' if policy.get('module_budget_pending',True)
                    or type(maximum) is not int or maximum<=0 else 'reward_module_cost_not_proven')
            stopped=self._record(page,record,frame,candidates,None,reason)
            return self._result(page,None,False,stopped,done=True)
        choice_index = 0
        if page == 'EVENT_CHOICE':
            options = choice_options(record.get('ocr'), record.get('size'))
            candidates = [box for box, _text in options]
            choice_index = preferred_choice(options,
                                            gift_hints(record.get('ocr'),
                                                       record.get('size')))
            from .event_vision import cyborg_city_choice
            try:
                city_choice=cyborg_city_choice(record.get('ocr'),record.get('size'),options)
            except ValueError as error:
                stopped=self._record(page,record,frame,candidates,None,str(error))
                return self._result(page,None,False,stopped,done=True)
            if city_choice is not None:
                choice_index=city_choice
                self.note('cyborg_city_choice',answer='No',source='current exact city question and Yes/No labels',
                          strategy='three No answers disable the factory; each page is freshly identified')
        if page == 'MAP':
            if self.theme_transaction is not None and self.theme_transaction.data.get('pending'):
                from .theme_vision import ThemeCatalog
                texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
                try:
                    self.theme_transaction.observe(self.run_id,map_header(texts,record.get('size') or (1920,1080)),
                                                   ThemeCatalog(ROOT/'assets/resource/base'),frame_file(directory))
                except ValueError as error:
                    stopped=self._record(page,record,frame,candidates,None,str(error))
                    return self._result(page,None,False,stopped,done=True)
            # A node the run has already sent a click to is not offered again on the
            # same floor: live run build/window-run76.json clicked one spot eight times,
            # each time opening the same gift tray over the map and confirming it away.
            # Only a *named* floor change starts a new floor and clears the tried set.
            header = map_header([Text(item['text'], tuple(item['box']), item['score'])
                                 for item in record.get('ocr') or []],
                                record.get('size') or (1920, 1080))
            floor = getattr(header, 'floor', None)
            state['map_progress'].note_floor(floor)
            state['floor_now'] = floor if page == 'MAP' else state['floor_now']
            if state['map_points']:
                # The calibration path: the caller names the points, so a floor whose
                # nodes the frame does not read can still be walked while the reading
                # is being fixed. Scale is taken from the frame, not assumed.
                frame_width = (record.get('size') or (1920, 1080))[0]
                scale = frame_width / 1280.0
                side = max(40, round(60 * scale))
                candidates = []
                for x, y in state['map_points']:
                    cx, cy = int(round(x * scale)), int(round(y * scale))
                    candidates.append([cx - side // 2, cy - side // 2, side, side])
            candidates = state['map_progress'].remaining(candidates)
        sha = record.get('image_sha256')
        if not settings.observe_only and page in WAIT_PAGES:
            state['unknown_seen'] += 1
            if state['unknown_seen'] > settings.unknown_rounds:
                stopped = self._record(page, record, frame, candidates, None,
                                       'page_unreadable_after_waiting')
                return self._result(page, None, False, stopped)
            # Loading screens, turn animations and the battle result clear themselves;
            # they are not a refusal, so wait them out instead of stopping the window.
            self.note('window_unknown_wait', page=page, round=state['unknown_seen'],
                      interval_s=settings.interval)
            time.sleep(settings.interval)
            return self._result(page, None, False, None, waiting=True)
        state['unknown_seen'] = 0
        if not settings.observe_only and page == 'TUTORIAL' and sha in state['tutorial_cards']:
            stopped = self._record(page, record, frame, candidates, None,
                                   'tutorial_card_repeated')
            return self._result(page, None, False, stopped, done=True)
        if page == 'TUTORIAL' and sha:
            state['tutorial_cards'].add(sha)
        if page in BATTLE_PAGES:
            # The battle is exempt from the repeated-plan guard because assigning and
            # submitting legitimately repeat the same two controls for many turns, but
            # it is not exempt from progress: the wave and turn readouts have to move.
            signature = (record.get('wave'), record.get('turn'))
            if signature == state['battle_sig']:
                state['battle_rounds'] += 1
            else:
                state['battle_sig'], state['battle_rounds'] = signature, 1
            if state['battle_rounds'] > settings.battle_rounds:
                stopped = self._record(page, record, frame, candidates, None,
                                       'battle_progress_stalled')
                return self._result(page, None, False, stopped, done=True)
        team = team_state(record, self.controls) if page == 'PRE_BATTLE_TEAM' else None
        if page=='DEPLOYMENT_RESET':
            d=self.deployment_transaction.data if self.deployment_transaction else None
            pending=d.get('pending') if d else None
            team={'reset_pending':bool(d and d['scope']==self.run_id and pending
                  and pending['kind']=='clear' and not pending.get('confirm_sent'))}
        if team is not None:
            from .storage import ProfileStore, SINNERS
            slot = self.store.team_slot if self.store is not None else settings.team
            from .runtime_paths import data_directory
            profiles = ProfileStore(data_directory(ROOT) / 'user-team-profiles.json')
            if profiles.path.exists():
                saved = next((t for t in profiles.load() if t.slot == slot), None)
                if saved is not None and saved.deployment:
                    team['order'] = [SINNERS.index(sinner) + 1 for sinner in saved.deployment]
        if page=='PRE_BATTLE_TEAM' and team is not None and team.get('order'):
            if self.deployment_transaction is None or not team.get('participants'):
                stopped=self._record(page,record,frame,candidates,None,'deployment_transaction_or_counter_missing')
                return self._result(page,None,False,stopped,done=True)
            try:
                pending=self.deployment_transaction.data.get('pending') if self.deployment_transaction.data else None
                if pending and self.deployment_transaction.data['scope']==self.run_id:
                    if pending['kind']=='clear' and team['participants'][0]==0:
                        self.deployment_transaction.observe(tuple(team['participants']))
                    elif (pending['kind']=='card' and team['participants'][0]==pending['before']+1
                          and team['states'][pending['card']-1] in ('selected','backup')):
                        self.deployment_transaction.observe(tuple(team['participants']))
                team.update(self.deployment_transaction.prepare(self.run_id,team['order'],tuple(team['participants'])))
            except ValueError as error:
                stopped=self._record(page,record,frame,candidates,None,str(error))
                return self._result(page,None,False,stopped,done=True)
        if page == 'DUNGEON_TEAM':
            from .team_vision import selected_saved_team
            # A click is intent; the fresh TEAMS header proves which slot is selected.
            texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
            team = {'wanted': self.store.team_slot if self.store is not None
                    else settings.team,
                    'selected': selected_saved_team(texts,record.get('size') or (1920,1080))}
        else:
            state['team_slot_picked'] = None
        defeat = None
        if page == 'BATTLE_DEFEAT':
            # A wipe is the one page where the run's survival is decided. The row is
            # sent once, then its own Confirm; a retry is counted only when that Confirm
            # has landed, so --defeat-tries counts finished retries and a retry in
            # flight is never cut in half. Once the tries are spent nothing is sent at
            # all and the decision goes back to the player, unless --defeat-accept.
            spent = (not state['defeat_row_sent']
                     and state['defeat_attempts'] >= max(1, settings.defeat_tries))
            defeat = {'row_sent': state['defeat_row_sent'], 'spent': spent,
                      'accept': bool(settings.defeat_accept)}
            if spent:
                self.note('window_defeat', page=page, retries=state['defeat_attempts'],
                          sent=bool(settings.defeat_accept))
        else:
            state['defeat_row_sent'] = False
        reward = reward_state(record) if page == 'REWARD_CARD' else None
        gift, cards = None, None
        floor_offers=None
        if page == 'GIFT_PICK':
            gift = gift_state(record, image=latest_frame(directory)[0],
                              select_box=self.controls.get('gift_pick.select_button'),
                              picks=state['gift_picks'])
            cards = gift_cards([Text(item['text'], tuple(item['box']), item['score'])
                                for item in record.get('ocr') or []],
                               record.get('size') or (1920, 1080))
            from . import floor_gifts
            from .gift_vision import GiftCatalog
            from .storage import ProfileStore
            try:
                if self.floor_gift_transaction is None:
                    raise ValueError('floor_gift_transaction_missing')
                if self.floor_gift_catalog is None:
                    self.floor_gift_catalog=GiftCatalog(ROOT/'assets/resource/base')
                texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
                floor_offers,gift=floor_gifts.observe(texts,record.get('size') or (1920,1080),self.floor_gift_catalog,
                    image=latest_frame(directory)[0],select_box=self.controls.get('gift_pick.select_button'))
                d=self.floor_gift_transaction.prepare(self.run_id,floor_offers,gift,frame_file(directory))
                profile=next((p for p in ProfileStore(self.store.path.parent/'user-team-profiles.json').load()
                              if p.slot==self.store.team_slot),None)
                if profile is None:raise ValueError('floor_gift_saved_team_missing')
                ranking=floor_gifts.rank(floor_offers,profile,d['selected'])
                gift['ranking']=ranking
                owned_single=(len(floor_offers)==1 and floor_offers[0].owned
                    and floor_offers[0].selection_source=='single_free_select_button'
                    and gift['chosen']==0 and not d['selected'])
                if owned_single:
                    from .vision import find
                    refuse=find(texts,r'^Refuse Gift$',(.68,.77,.80,.84),record['size'],.9)
                    if len(refuse)!=1:raise ValueError('owned_gift_refuse_control_missing')
                    gift.update(refuse_owned=True,refuse_target=list(refuse[0].box))
                elif gift['chosen']<gift['required']:
                    if not ranking:raise ValueError('floor_gift_no_allowed_offer')
                    selected=next(o for o in floor_offers if o.title==ranking[0]['title'])
                    gift.update(target=list(selected.box),title=selected.title)
                self.note('floor_gift_ranking',team=profile.slot,ranking=ranking,
                          selected=d['selected'],selection_source=floor_offers[0].selection_source,
                          proof=str(frame_file(directory)))
            except (ValueError,FileNotFoundError) as error:
                stopped=self._record(page,record,frame,candidates,None,str(error))
                return self._result(page,None,False,stopped,done=True)
        else:
            state['gift_picks'] = 0
        floor_receipt=None
        floor_tx=self.floor_gift_transaction
        if floor_tx is not None and floor_tx.data and floor_tx.data['scope']==self.run_id and floor_tx.data['commit_sent'] and not floor_tx.data['completed']:
            from . import initial_gifts
            texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
            floor_receipt=initial_gifts.receipt_name(texts,record.get('size') or (1920,1080))
            d=floor_tx.data
            remaining=[n for n in d['selected'] if n not in [r['title'] for r in d['receipts']]]
            if (page!='GIFT_GET' or not d['pending'] or d['pending']['kind']!='commit'
                or not any(initial_gifts.same_name(floor_receipt,n) for n in remaining)):
                stopped=self._record(page,record,frame,candidates,None,'floor_gift_receipt_unknown_repeated_or_pending')
                return self._result(page,None,False,stopped,done=True)
        plan_controls=dict(self.controls)
        if page=='EVENT_RESULT':
            from .event_vision import factory_result_panel
            box=factory_result_panel(record.get('ocr'),record.get('size') or (1920,1080))
            if box:plan_controls['factory_result.result_panel']=list(box)
        if page=='DEPLOYMENT_RESET':
            from .vision import deployment_reset_confirm
            texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
            box=deployment_reset_confirm(texts,record.get('size') or (1920,1080))
            if box:plan_controls['deployment_reset.confirm']=list(box)
        if page=='PRE_BATTLE_TEAM':
            from .map_vision import pre_battle_team_page
            texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
            current_team=pre_battle_team_page(texts,record.get('size') or (1920,1080))
            if current_team is not None:
                # Clear Selection is a page identity anchor, not a static control.
                # Bind its fresh, paired caption before asking the planner to reset.
                plan_controls['pre_battle.clear_selection']=list(current_team.clear_selection.box)
        initial = None
        if page == 'INITIAL_GIFTS':
            from . import initial_gifts
            records = [Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
            size=record.get('size') or (1920,1080)
            count=initial_gifts.counter(records,size)
            image,_=latest_frame(directory)
            if count is None or self.initial_transaction is None:
                stopped=self._record(page,record,frame,candidates,None,'initial_gift_counter_or_transaction_missing')
                return self._result(page,None,False,stopped,done=True)
            try:
                d=self.initial_transaction.prepare(self.run_id,settings.gift_keyword,count,frame_file(directory))
            except ValueError as error:
                stopped=self._record(page,record,frame,candidates,None,str(error))
                return self._result(page,None,False,stopped,done=True)
            chosen,required=count
            point=reason=gift=None
            rows=[initial_gifts.row_target(records,size,i) for i in (1,2,3)]
            if chosen<required:
                preferences=wanted_gifts(state['gift_plan'],settings.gift_keyword,fallback=())
                selected={x['title'] for x in d['selected']}
                candidates_by_name={r[1]:(i+1,r[0]) for i,r in enumerate(rows) if r is not None}
                match=next((n for n in preferences if n in candidates_by_name and n not in selected),None)
                if match:
                    row,box=candidates_by_name[match]
                    point=(box[0]+box[2]//2,box[1]+box[3]//2)
                    gift=dict(row=row,title=match)
                    reason='the_starting_gift_row_is_taken_from_the_tray'
                elif not any(rows):
                    box=initial_gifts.group_target(records,size,settings.gift_keyword.title())
                    if box:point=(box[0]+box[2]//2,box[1]+box[3]//2)
                else:
                    stopped=self._record(page,record,frame,candidates,None,'configured_initial_gift_not_offered')
                    return self._result(page,None,False,stopped,done=True)
            elif initial_gifts.selected_rows(image)!=sorted(x['row'] for x in d['selected']):
                stopped=self._record(page,record,frame,candidates,None,'initial_gift_selected_rows_not_proven')
                return self._result(page,None,False,stopped,done=True)
            initial=dict(chosen=chosen,required=required,point=point,
                         keyword=settings.gift_keyword if gift is None else None,reason=reason,gift=gift)
        if page=='GIFT_GET' and self.initial_transaction is not None:
            d=self.initial_transaction.data
            if d and d['scope']==self.run_id and len(d.get('acknowledged',[]))<len(d['selected']):
                from . import initial_gifts
                from .storage import write_json
                records=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
                title=initial_gifts.receipt_name(records,record.get('size') or (1920,1080))
                expected=d['selected'][len(d.get('acknowledged',[]))]['title']
                if d.get('receipt_pending') or not initial_gifts.same_name(title,expected):
                    stopped=self._record(page,record,frame,candidates,None,'initial_gift_receipt_not_proven_or_pending')
                    return self._result(page,None,False,stopped,done=True)
                state['initial_receipt']=dict(title=expected,proof=str(frame_file(directory)))
        if page=='DUNGEON_TEAM' and self.store is not None and not settings.observe_only and not state.get('entry_reconciled'):
            reconcile(self.store,page=page,proof=frame_file(directory))
            self.run_id=self.store.start()
            state['entry_reconciled']=True
            state['run_settled_itself']=False
            if self.grace_transaction is not None:
                self.grace_transaction.begin(self.run_id,state['grace_wanted'],settings.grace_budget,
                                             frame_file(directory))
        graces = None
        transaction=self.grace_transaction
        if page in ('STAR_GRACES','STAR_CONFIRM') and transaction is not None:
            try:
                records=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
                available=available_starlight(records,record.get('size') or (1920,1080))
                d=transaction.validate(self.run_id,state['grace_wanted'],settings.grace_budget,available)
                state['grace_bought']=set(d['selected'])
            except ValueError as error:
                stopped=self._record(page,record,frame,candidates,None,str(error))
                return self._result(page,None,False,stopped,done=True)
        if page=='STAR_CONFIRM' and transaction is not None:
            from .grace_vision import conversion_state
            image,_=latest_frame(directory)
            graces=conversion_state(image,records,ROOT/'assets/resource/base/image/navigation')
            complete=set(transaction.data['selected'])==set(state['grace_wanted'])
            graces.update(complete=complete,incomplete=not complete)
        if page == 'STAR_GRACES':
            records = [Text(item['text'], tuple(item['box']), item['score'])
                       for item in record.get('ocr') or []]
            available = available_starlight(records, record.get('size') or (1920, 1080))
            if available is None:
                stopped = self._record(page, record, frame, candidates, None,
                                       'starlight_available_balance_not_proven')
                return self._result(page, None, False, stopped, done=True)
            from .grace_vision import observed_board
            image, _ = latest_frame(directory)
            board=observed_board(image,records,state['grace_wanted']) if image is not None else None
            if board is None:
                stopped=self._record(page,record,frame,candidates,None,'configured_grace_costs_not_proven')
                return self._result(page,None,False,stopped,done=True)
            spent = sum(board['costs'][index-1] for index in state['grace_bought'])
            total_budget = min(settings.grace_budget, available + spent)
            wanted = plan_purchases(state['grace_wanted'], total_budget,
                                    bought=state['grace_bought'], costs=board['costs'])
            points = board['points']
            self.journal.record('grace_purchase_plan', requested=state['grace_wanted'],
                                bought=sorted(state['grace_bought']), available=available,
                                budget=settings.grace_budget, costs=board['costs'], next=wanted)
            remaining = set(state['grace_wanted']) - state['grace_bought']
            if remaining and not wanted:
                stopped=self._record(page,record,frame,candidates,None,
                                     'configured_graces_incomplete_within_budget')
                return self._result(page,None,False,stopped,done=True)
            if wanted and wanted[0] in points:
                graces = {'card': wanted[0], 'point': points[wanted[0]],
                          'available': available}
        elif page!='STAR_CONFIRM':
            state['grace_bought'] = set()
        check = check_of(directory, record, page=page)
        arrows = arrows_of(directory)
        difficulty = None
        theme_choice=None
        if page == 'THEME_PACKS':
            from .theme_vision import ThemeCatalog, theme_page
            image, _ = latest_frame(directory)
            if image is not None:
                texts = [Text(t['text'], tuple(t['box']), t['score']) for t in record.get('ocr', [])]
                locale = json.loads((ROOT/'assets/resource/en/locale.json').read_text(encoding='utf-8'))
                difficulty = theme_page(image, ThemeCatalog(ROOT/'assets/resource/base'), texts, locale)
            if difficulty=='normal' and self.store is not None:
                from .storage import read_json
                from .vision import find
                path=self.store.path.parent/'user-difficulty-transaction.json'
                progress=read_json(path) if path.exists() else {}
                mode_boxes=ThemeCatalog(ROOT/'assets/resource/base').matches(image,'normal_mode',(.61,0,.83,.13))
                header=find(texts,r'^SELECT\s*FLOOR\s*1\s*THEME\s*PACK$',(.38,.13,.63,.20),(1920,1080),.85)
                if progress.get('pending'):
                    stopped=self._record(page,record,frame,candidates,None,'difficulty_switch_pending')
                    return self._result(page,None,False,stopped,done=True)
                if len(header)==1 and len(mode_boxes)==1 and not (progress.get('scope')==self.run_id and progress.get('hard')):
                    x,y,w,h=mode_boxes[0]
                    plan_controls['theme_packs.enable_hard']=[x+110,y+13,40,24]
            if difficulty=='hard':
                from .theme_vision import pack_candidates,recommend_pack
                from .storage import ProfileStore
                from .vision import find
                if self.theme_transaction is None or self.theme_transaction.data.get('pending'):
                    stopped=self._record(page,record,frame,candidates,None,'theme_transaction_missing_or_pending')
                    return self._result(page,None,False,stopped,done=True)
                profiles=ProfileStore(self.store.path.parent/'user-team-profiles.json').load()
                profile=next((p for p in profiles if p.slot==self.store.team_slot),None)
                cat=ThemeCatalog(ROOT/'assets/resource/base')
                choices=pack_candidates(image,texts,cat)
                headers=find(texts,r'^SELECT\s*FLOOR\s*[1-5]\s*THEME\s*PACK$',(.38,.13,.63,.20),(image.shape[1],image.shape[0]),.85)
                theme_choice,ranking=recommend_pack(choices,profile) if profile else (None,[])
                if not theme_choice or len(headers)!=1:
                    stopped=self._record(page,record,frame,candidates,None,'theme_candidates_profile_or_floor_not_proven')
                    return self._result(page,None,False,stopped,done=True)
                import re
                theme_choice['floor']=int(re.search(r'[1-5]',headers[0].text).group())
                x,y,w,h=theme_choice['box'];scale=image.shape[1]/1280
                plan_controls['theme_packs.pack_01']=[int(x+w/2-20),int(y+70*scale-12),40,24]
                plan_controls['theme_packs.pull_to']=[int(x+w/2-20),int(image.shape[0]*.925-12),40,24]
                self.note('theme_pack_recommendation',chosen=theme_choice,ranking=ranking,required='hard')
            self.journal.record('difficulty_gate', difficulty=difficulty,
                                frame=frame, required='hard', verified_clear=False)
        plan = plan_step(page, controls=plan_controls, arrows=arrows,
                         difficulty=difficulty,
                         start_box=record.get('start_box'),
                         auto_assign=record.get('auto_assign_buttons'),
                         candidates=candidates, candidate_index=choice_index,
                         team=team, reward=reward, gift=gift, cards=cards,
                         graces=graces, initial=initial, check=check, defeat=defeat,
                         search={'mode': settings.gift_search},
                         bonus={'spend': state['run_settled_itself']})
        if page=='UNKNOWN_DIALOG' and self.floor_gift_transaction is not None:
            from .floor_gift_transaction import refusal_confirm_target
            d=self.floor_gift_transaction.data;p=d.get('pending') if d else None
            target=refusal_confirm_target(record)
            if (d and d['scope']==self.run_id and p and p['kind']=='refuse_owned'
                and not p.get('confirm_sent') and target):
                plan=dict(page=page,action='click',target=target,node=None,
                    expect=['MAP','REWARD_CARD','UNKNOWN'],advance=False,
                    reason='confirm_proven_owned_gift_refusal')
        entry = {'step': state['step'], 'page_before': page, 'scene_before': record['scene'],
                 'frame': frame, 'observation': record, 'plan': plan, 'team': team,
                 'reward': reward, 'gift': gift, 'cards': cards, 'graces': graces,
                 'initial': initial, 'search': {'mode': settings.gift_search},
                 'check': check, 'defeat': defeat,
                 'bonus': {'spend': state['run_settled_itself']},
                 'arrows': arrows, 'candidates': candidates}
        if plan['action'] not in ('click', SWIPE, NODE) or settings.observe_only:
            entry.update(step_result(plan, sent=False, before=page, after=None, page=page))
            entry['stopped'] = ('observe_only' if settings.observe_only
                                else plan['reason'])
            # A refusal that says the reading is missing can be the frame's fault rather
            # than the page's: live build/window-run86.json refused the picked skill check
            # because the frame it settled on was the roll's transition, and Commence
            # arrived on the next one. Looking again costs one interval, sends no input,
            # and page_tries bounds it.
            retry_reading = (not settings.observe_only and plan.get('target') is None
                             and plan.get('reason', '').startswith('no_')
                             and state['page_attempts'] + 1 < max(1, settings.page_tries))
            self.artifacts['steps'].append(entry)
            if retry_reading:
                state['page_attempts'] += 1
                entry['stopped'] = 'page_reading_retried'
                self.note('window_page_retry', reason=plan.get('reason'),
                          attempt=state['page_attempts'])
                time.sleep(settings.interval)
                return self._result(page, plan.get('target'), False, None, waiting=True)
            if settings.observe_only and state['step'] + 1 < settings.steps:
                state['step'] += 1
                time.sleep(settings.interval)
                return self._result(page, plan.get('target'), False, None, waiting=True)
            return self._result(page, plan.get('target'), False, entry['stopped'], done=True)
        if plan.get('reason')=='dungeon_team_confirm_brings_the_chosen_team_in' and self.store is not None:
            self.store.entry_intent(self.run_id,team['selected'],frame_file(directory))
        if plan.get('reason')=='the_level_warning_proceeds_with_the_rotation_team' and self.store is not None:
            self.store.entry_warning_intent(self.run_id,frame_file(directory))
        if page=='STAR_GRACES' and (plan.get('detail') or {}).get('card') and transaction is not None:
            card=plan['detail']['card']
            transaction.intent(card,board['costs'][card-1],available,frame_file(directory))
        if page=='INITIAL_GIFTS' and (initial or {}).get('gift'):
            g=initial['gift'];self.initial_transaction.intent(g['row'],g['title'],count,frame_file(directory))
        if page=='GIFT_PICK' and (gift or {}).get('title'):
            self.floor_gift_transaction.intent(gift['title'],
                dict(chosen=gift['chosen'],required=gift['required']),frame_file(directory))
        if plan.get('reason')=='refuse_proven_owned_single_free_gift':
            self.floor_gift_transaction.refuse_owned(floor_offers,
                dict(chosen=gift['chosen'],required=gift['required']),frame_file(directory))
        if plan.get('reason')=='confirm_proven_owned_gift_refusal':
            self.floor_gift_transaction.refusal_confirm_intent(self.run_id,frame_file(directory))
        if plan.get('reason')=='select_takes_the_picked_floor_gifts':
            self.floor_gift_transaction.commit(frame_file(directory))
        if floor_receipt:
            self.floor_gift_transaction.receipt_intent(floor_receipt,frame_file(directory))
        if page=='GIFT_GET' and state.get('initial_receipt'):
            from .storage import write_json
            self.initial_transaction.data['receipt_pending']=state['initial_receipt']
            write_json(self.initial_transaction.path,self.initial_transaction.data)
        if plan.get('reason')=='enable_hard_on_proven_floor_one':
            from .storage import write_json
            path=self.store.path.parent/'user-difficulty-transaction.json'
            write_json(path,dict(scope=self.run_id,pending=dict(before='normal',requested='hard',proof=str(frame_file(directory)))))
        if plan.get('reason')=='the_floor_theme_pack_is_pulled_down_to_be_taken':
            self.theme_transaction.intent(self.run_id,theme_choice['floor'],theme_choice['name'],frame_file(directory))
        if page=='PRE_BATTLE_TEAM' and plan.get('reason') in ('clear_inherited_participant_order_before_saved_deployment','team_card_joins_the_next_unpicked_identity'):
            kind='clear' if plan['reason'].startswith('clear_inherited') else 'card'
            self.deployment_transaction.intent(kind,tuple(team['participants']),(plan.get('detail') or {}).get('card_index'))
        point = None
        if plan.get('reason')=='confirm_pending_deployment_reset_once':
            self.deployment_transaction.confirm_clear(self.run_id)
        if plan.get('reason')=='battle_button_submits_the_team' and self.deployment_transaction is not None:
            from .storage import write_json
            self.deployment_transaction.data['submit_pending']=True
            write_json(self.deployment_transaction.path,self.deployment_transaction.data)
        delay = random.randint(350, 750)
        if plan['action'] == NODE:
            self.note('window_intent', page=page, node=plan['node'],
                      reason=plan['reason'], delay_ms=delay)
            if self.tasker is None:
                raise RuntimeError('a node plan needs a Maa tasker')
            run_node(self.tasker, plan['node'], self.deadline)
        elif plan['action'] == SWIPE:
            # A drag's start point is jittered inside its anchored box just like a click,
            # and its end point is jittered around the anchored pull target (``to`` is a
            # point, not a box); MuMu only ever sees Maa's simulated touch.
            start = inset_box(tuple(plan['target']), .3)
            point = (random.randint(start[0], start[0] + max(1, start[2])),
                     random.randint(start[1], start[1] + max(1, start[3])))
            target_x, target_y = (int(value) for value in plan['to'])
            drop = (target_x + random.randint(-8, 8), target_y + random.randint(-8, 8))
            duration = int(plan.get('duration_ms') or 600)
            self.note('window_intent', page=page, target=list(plan['target']),
                      reason=plan['reason'], point=list(point), swipe_to=list(drop),
                      duration_ms=duration, delay_ms=delay)
            self.device.swipe(point[0], point[1], drop[0], drop[1], duration)
        else:
            box = inset_box(tuple(plan['target']), .3)
            x, y, w, h = box
            point = (random.randint(x, x + max(1, w)), random.randint(y, y + max(1, h)))
            self.note('window_intent', page=page, target=list(plan['target']),
                      reason=plan['reason'], point=list(point), delay_ms=delay)
            self.device.click(*point)
        self.artifacts['clicks_sent'] += 1
        if page == 'MAP' and plan.get('target') is not None:
            # Whether or not the click opened anything, that spot has had its turn:
            # live run build/window-run76.json opened the same gift tray eight times
            # because a click that did open something was never remembered.
            state['map_progress'].note_click(plan['target'])
        entry.update(click_point=None if point is None else list(point), delay_ms=delay)
        time.sleep(delay / 1000)
        settled, settled_page = None, None
        before_sha = record.get('image_sha256')
        for index in range(max(1, settings.rounds)):
            if index:
                time.sleep(settings.interval)
            settled = self._observe()
            settled_page = resolve_scene(self.registry, directory, settled)
            if settled_page not in (page, 'UNKNOWN'):
                break
            # A tutorial card keeps the same page label but changes the pixels, so a
            # changed frame is the only evidence that the click landed.
            # Select can first show CONNECTING on the same gift offer. That pixel
            # change is not a named GET receipt; spend the remaining read-only
            # settle rounds without sending Select again.
            awaiting_gift_receipt = plan.get('reason') == 'select_takes_the_picked_floor_gifts'
            if (not awaiting_gift_receipt
                    and settled.get('image_sha256') not in (None, before_sha)):
                break
        if page=='DUNGEON_TEAM' and settled_page!='DUNGEON_TEAM':state['entry_reconciled']=False
        entry.update(page_after=settled_page, settled=settled,
                     scene_after=settled['scene'])
        if settled_page not in (None, 'MAP', 'UNKNOWN'):
            # The step landed off the map, so this map visit is over and its spots may
            # be walked again when the page comes back: live window build/
            # window-run-continue-4.json returned from the event behind the "?" node to
            # the same map, where that node was still the forward step.
            state['map_progress'].leave()
        entry.update(step_result(plan, sent=True, before=page, after=settled_page,
                                 page=settled_page,
                                 frame_changed=(settled.get('image_sha256')
                                                not in (None, before_sha))))
        if page=='STAR_GRACES' and (plan.get('detail') or {}).get('card') and transaction is not None:
            try:
                observed=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
                after_available=available_starlight(observed,settled.get('size') or (1920,1080))
                if settled_page!='STAR_GRACES':raise ValueError('Grace purchase left selection unexpectedly')
                transaction.observe(after_available,frame_file(directory))
            except ValueError as error:
                entry.update(passed=False,reason=str(error),stopped='unverified_grace_purchase')
        if page=='INITIAL_GIFTS' and (initial or {}).get('gift'):
            try:
                from . import initial_gifts
                post_records=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
                post_count=initial_gifts.counter(post_records,settled.get('size') or (1920,1080))
                post_image,_=latest_frame(directory)
                self.initial_transaction.observe(post_count,initial_gifts.selected_rows(post_image),frame_file(directory))
            except ValueError as error:
                entry.update(passed=False,reason=str(error),stopped='unverified_initial_gift_selection')
        if page=='GIFT_PICK' and (gift or {}).get('title'):
            try:
                from . import floor_gifts
                if settled_page!='GIFT_PICK':raise ValueError('floor_gift_selection_left_page')
                post_records=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
                post_offers,post_count=floor_gifts.observe(post_records,settled.get('size') or (1920,1080),self.floor_gift_catalog,
                    image=latest_frame(directory)[0],select_box=self.controls.get('gift_pick.select_button'))
                self.floor_gift_transaction.observe_pick(post_offers,post_count,frame_file(directory))
            except ValueError as error:
                entry.update(passed=False,reason=str(error),stopped='unverified_floor_gift_selection')
        if plan.get('reason')=='select_takes_the_picked_floor_gifts':
            from . import initial_gifts
            post_records=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
            title=initial_gifts.receipt_name(post_records,settled.get('size') or (1920,1080))
            if settled_page!='GIFT_GET' or not any(initial_gifts.same_name(title,n) for n in self.floor_gift_transaction.data['selected']):
                entry.update(passed=False,reason='floor_gift_commit_receipt_not_proven',stopped='unverified_floor_gift_commit')
        if plan.get('reason') in ('refuse_proven_owned_single_free_gift','confirm_proven_owned_gift_refusal'):
            try:
                self.floor_gift_transaction.observe_refusal(settled_page,frame_file(directory),
                    map_floor=settled.get('floor'),
                    next_reward_offer=unselected_reward_successor(settled) if settled_page=='REWARD_CARD' else None)
            except ValueError as error:
                entry.update(passed=False,reason=str(error),stopped='unverified_floor_gift_refusal')
        if floor_receipt:
            try:
                from . import initial_gifts
                post_records=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
                title=initial_gifts.receipt_name(post_records,settled.get('size') or (1920,1080))
                next_free=None
                if settled_page=='GIFT_PICK':
                    from .floor_gifts import observe as observe_gifts
                    offers,count=observe_gifts(post_records,settled.get('size') or (1920,1080),self.floor_gift_catalog,
                        image=latest_frame(directory)[0],select_box=self.controls.get('gift_pick.select_button'))
                    if count==dict(chosen=0,required=1) and all(o.selection_source.endswith('_free_select_button') for o in offers):
                        next_free=dict(count=count,source=offers[0].selection_source,
                            offer=self.floor_gift_transaction.signature(offers))
                self.floor_gift_transaction.observe_receipt(settled_page,title,frame_file(directory),
                    next_free_offer=next_free,
                    next_reward_offer=unselected_reward_successor(settled) if settled_page=='REWARD_CARD' else None)
            except ValueError as error:
                entry.update(passed=False,reason=str(error),stopped='unverified_floor_gift_receipt')
        if page=='GIFT_GET' and state.get('initial_receipt'):
            from . import initial_gifts
            from .storage import write_json
            post_records=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
            post_title=initial_gifts.receipt_name(post_records,settled.get('size') or (1920,1080))
            current=state['initial_receipt']['title']
            successor=(settled_page in ('GIFT_SEARCH','THEME_PACKS','MAP') or
                       (settled_page=='GIFT_GET' and post_title and not initial_gifts.same_name(post_title,current)))
            if successor:
                d=self.initial_transaction.data
                d.setdefault('acknowledged',[]).append(dict(title=current,receipt=state['initial_receipt']['proof'],successor=str(frame_file(directory))))
                d['receipt_pending']=None;write_json(self.initial_transaction.path,d)
                state['initial_receipt']=None
            else:entry.update(passed=False,reason='initial_gift_receipt_successor_not_proven',stopped='unverified_initial_receipt')
        if plan.get('reason')=='enable_hard_on_proven_floor_one':
            from .theme_vision import theme_page,ThemeCatalog
            from .storage import write_json
            image,_=latest_frame(directory)
            texts=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
            locale=json.loads((ROOT/'assets/resource/en/locale.json').read_text())
            mode=theme_page(image,ThemeCatalog(ROOT/'assets/resource/base'),texts,locale)
            if mode=='hard':
                write_json(path,dict(scope=self.run_id,pending=None,hard=True,proof=str(frame_file(directory))))
            else:entry.update(passed=False,reason='hard_switch_successor_not_proven',stopped='unverified_hard_switch')
        if plan.get('reason')=='the_floor_theme_pack_is_pulled_down_to_be_taken':
            from .theme_vision import ThemeCatalog
            texts=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
            try:
                self.theme_transaction.observe(self.run_id,map_header(texts,settled.get('size') or (1920,1080)),
                                               ThemeCatalog(ROOT/'assets/resource/base'),frame_file(directory))
            except ValueError as error:
                entry.update(passed=False,reason=str(error),stopped='unverified_theme_drag')
        if ((page=='PRE_BATTLE_TEAM' and plan.get('reason') in ('clear_inherited_participant_order_before_saved_deployment','team_card_joins_the_next_unpicked_identity'))
                or plan.get('reason')=='confirm_pending_deployment_reset_once'):
            try:
                post_records=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
                if not (plan['reason']=='clear_inherited_participant_order_before_saved_deployment' and settled_page=='DEPLOYMENT_RESET'):
                    self.deployment_transaction.observe(participants(post_records,settled.get('size') or (1920,1080)))
            except ValueError as error:entry.update(passed=False,reason=str(error),stopped='unverified_deployment_input')
        if plan.get('reason')=='battle_button_submits_the_team' and self.deployment_transaction is not None:
            from .storage import write_json
            self.deployment_transaction.data['submitted']=settled_page in ('BATTLE_HUD','DEPLOYMENT')
            self.deployment_transaction.data['submit_pending']=settled_page not in ('BATTLE_HUD','DEPLOYMENT')
            write_json(self.deployment_transaction.path,self.deployment_transaction.data)
        if self.store is not None and entry['passed']:
            # Every completed step is offered to the ledger; only the page that proves
            # an event (a floor's map, the run summary, the reward modal's Confirm, the
            # loadout Confirm) settles one -- and a page may settle two, in order.
            ledger = record_ledger_event(self.store, self.run_id, directory, page, plan,
                                         state['floor_now'], self.journal)
            if ledger:
                entry['ledger_events'] = [dict(kind=event.kind, floor=event.floor)
                                          for event in ledger]
                if any(event.kind in ('final_victory', 'reward_received')
                       for event in ledger):
                    # This run reached its payout, so the weekly-bonus question that
                    # follows the claim may spend one. Only three exist per week and they
                    # do not carry over, so a run that was given up asks the other way
                    # round and keeps them.
                    state['run_settled_itself'] = True
            # An expired session is not a completion: the game threw the run away and
            # this Confirm claims what it left behind, so the run is filed as abandoned
            # and the rotation stays on the same team.
            expired = expire(self.store, page=page, reason=plan.get('reason'),
                             proof=frame_file(directory),
                             on_event=lambda run: self.note(
                                 'run_expired', run=run.get('id'),
                                 evidence=str(frame_file(directory))))
            if expired is not None:
                entry['ledger_expired'] = expired.get('id')
                state['run_settled_itself'] = False
            # A run the game no longer holds is filed too: the loadout picker is only
            # drawn for a new dungeon, so seeing it while the ledger still calls a run
            # active means that run ended without a receipt and the ledger would
            # otherwise never open the next one.
        detail = plan.get('detail') or {}
        if entry['passed'] and detail.get('slot'):
            # The loadout slot has been sent; the next step on this page must fall
            # through to Confirm instead of pressing the same slot again.
            state['team_slot_picked'] = detail['slot']
        if entry['passed'] and plan.get('reason') == 'the_wiped_stage_is_picked_for_a_retry':
            # The retry row is highlighted; the next step on this dialog sends its own
            # Confirm, and no further row is picked.
            state['defeat_row_sent'] = True
        if entry['passed'] and plan.get('reason') == 'the_retry_is_confirmed_and_the_stage_starts_over':
            # One retry is now committed; the budget counts finished retries.
            state['defeat_attempts'] += 1
            state['defeat_row_sent'] = False
        if entry['passed'] and detail.get('card'):
            # That grace is paid for; the next step buys the next affordable card.
            state['grace_bought'].add(detail['card'])
        if not entry['passed'] and entry['reason'] == 'unexpected_successor':
            # Live run build/window-run36 pressed To Battle! on a full 12/12 team page,
            # and the settle loop still read PRE_BATTLE_TEAM while the game had already
            # moved into the battle: the successor arrives after the transition, so one
            # more observation decides whether the input was swallowed or the frame was
            # merely early. No second input is sent.
            time.sleep(settings.interval)
            late = self._observe()
            late_page = resolve_scene(self.registry, directory, late)
            if late_page != page:
                entry.update(page_after=late_page, settled=late,
                             scene_after=late['scene'], late_observation=True)
                entry.update(step_result(plan, sent=True, before=page, after=late_page,
                                         page=late_page,
                                         frame_changed=(late.get('image_sha256')
                                                        not in (None, before_sha))))
        self.artifacts['steps'].append(entry)
        if settings.stop_page and (entry.get('page_after') or page) == settings.stop_page:
            # The caller asked to hand control back the moment this page shows, so
            # nothing further is sent from it; the run keeps its state untouched.
            entry['stopped'] = 'stop_page_reached'
            self.note('window_stop_page', page=settings.stop_page, step=entry.get('step'))
            return self._result(page, plan.get('target'), True, entry['stopped'], done=True)
        if not entry['passed']:
            # The map fades in and out between nodes, so an observation caught mid-fade
            # carries no candidate at all (live build/window-run75.json step26 refused on
            # exactly such a frame while the next one had the shop node again). Waiting a
            # round is the whole fix, and map_attempts still bounds it.
            no_candidate = plan.get('reason') == 'no_candidate_node_observed'
            retryable = (page == 'MAP' and settled_page in ('MAP', 'UNKNOWN')
                         and (plan.get('target') is not None or no_candidate)
                         and state['map_attempts'] + 1 < max(1, settings.map_tries))
            if not retryable:
                entry['stopped'] = entry['reason']
                return self._result(page, plan.get('target'), True, entry['stopped'],
                                    done=True)
            state['map_attempts'] += 1
            if no_candidate:
                entry['stopped'] = 'map_candidates_not_observed_yet'
                time.sleep(settings.interval)
                return self._result(page, plan.get('target'), True, None, waiting=True)
            # An unreachable node swallows the click and the page stays MAP, so skip it
            # and let the next candidate be tried in its place.
            state['map_progress'].note_click(plan['target'])
            entry['stopped'] = 'map_click_opened_no_panel'
            self.note('window_map_retry', target=list(plan['target']),
                      attempt=state['map_attempts'],
                      remaining=len([box for box in candidates
                                     if tuple(box) != tuple(plan['target'])]))
            return self._result(page, plan.get('target'), True, None, waiting=True)
        state['map_attempts'] = 0
        state['page_attempts'] = 0
        if plan['reason'] == 'the_floor_gift_card_must_be_picked_before_select':
            state['gift_picks'] += 1
        if detail.get('keyword') and entry.get('passed'):
            state['initial_picked'] += 1
        # A plan that keeps succeeding while the page never moves on is a loop, not
        # progress: live run window-20261006-034009 passed twelve rounds of TUTORIAL then
        # To Battle! with nothing changing underneath. Battles are exempt because a fight
        # legitimately alternates the same two clicks for as many turns as it has waves.
        # The counts belong to one visit to one page: a run that leaves and comes back is
        # moving, so a page change starts the counts over -- even when the plan on this
        # page is exempt.
        if page != state['guard_page']:
            state['repeated_plans'] = {}
            state['guard_page'] = page
        # The claim family is guarded across pages, not within one: claiming the run
        # walks RUN_CLAIM -> RUN_REWARD_DIALOG -> RUN_REWARD_CONFIRM and back, so the
        # per-page counts above reset on every hop and can never see the loop. Leaving
        # the family resets this counter; staying in it is bounded by --claim-tries.
        if page in CLAIM_FAMILY:
            state['claim_steps'] += 1
            if state['claim_steps'] > max(1, settings.claim_tries):
                entry['passed'] = False
                entry['stopped'] = 'claim_family_made_no_progress'
                self.note('window_claim_guard', page=page, steps=state['claim_steps'],
                          reason=plan.get('reason'))
                return self._result(page, plan.get('target'), True, entry['stopped'],
                                    done=True)
        else:
            state['claim_steps'] = 0
        if page not in LOOP_GUARD_EXEMPT and plan.get('reason') not in LOOP_GUARD_EXEMPT_REASONS:
            key = (page, plan['action'], plan.get('node'),
                   None if plan.get('target') is None else tuple(plan['target']))
            state['repeated_plans'][key] = state['repeated_plans'].get(key, 0) + 1
            if state['repeated_plans'][key] >= max(2, settings.loop_guard):
                entry['passed'] = False
                entry['stopped'] = 'the_same_plan_repeated'
                self.note('window_loop_guard', plan=list(key),
                          repeats=state['repeated_plans'][key])
                return self._result(page, plan.get('target'), True, entry['stopped'],
                                    done=True)
        state['step'] += 1
        return self._result(page, plan.get('target'), True, None)

    def run(self, *, steps=300, interval=6.0, round_limit=5, deadline=None):
        """Walk the loop and return the final summary the CLI prints.

        ``steps`` bounds the walk (the CLI passes its own ``--steps`` budget once a
        flow has run), ``interval`` is the pause between steps, and ``round_limit``
        caps how many steps a single ``run`` call takes: the runner never walks
        forever on its own, and a caller that wants more calls ``run`` again.
        """
        settings = self.settings
        if deadline is not None:
            self.deadline = deadline
        goal = max(0, int(steps))
        if goal == 0 and not settings.observe_only:
            goal = max(0, int(settings.steps))
        walked = 0
        while self.state['step'] < goal and walked < max(0, int(round_limit)):
            result = self.step()
            if not result.get('waiting'):
                walked += 1
            if result.get('done'):
                break
            time.sleep(interval)
        return self.summary()

    # -- records -----------------------------------------------------------
    def _record(self, page, record, frame, candidates, plan, reason):
        """Append the record-only step the guard paths write, and return its stop."""
        self.artifacts['steps'].append({
            'step': self.state['step'], 'page_before': page, 'scene_before': record['scene'],
            'frame': frame, 'observation': record, 'plan': plan,
            'candidates': candidates, 'action': 'record', 'reason': reason,
            'passed': False, 'clicks_sent': 0, 'stopped': reason})
        return reason

    def _result(self, page, target, sent, stopped, *, done=False, waiting=False):
        """The public shape of one step."""
        entry = self.artifacts['steps'][-1] if self.artifacts['steps'] else None
        return {'page': page, 'reason': None if entry is None else entry.get('reason'),
                'target': target, 'input_sent': bool(sent),
                'event': self.last_event,
                'stopped': stopped, 'done': bool(done or stopped is not None),
                'waiting': bool(waiting), 'step': self.state['step'],
                'observation': None if entry is None else entry.get('observation')}

    def summary(self):
        """The end-of-window summary, filled into the caller's own result dict.

        Every key the caller already put in ``result`` keeps its position: the CLI
        builds ``pid``/``address``/``run_ledger``/``device`` before the window starts,
        and the summary must add to that record rather than replace it.
        """
        settings = self.settings
        result = self.result
        result.setdefault('pid', os.getpid())
        result.setdefault('address', settings.address)
        result.setdefault('controller', 'Maa AdbController')
        result.setdefault('observe_only', bool(settings.observe_only))
        result.setdefault('steps', self.artifacts['steps'])
        result.setdefault('clicks_sent', self.artifacts['clicks_sent'])
        result.setdefault('verified_clear', self.artifacts['verified_clear'])
        result.setdefault('foreground_before', None)
        if self.store is not None and self.run_id is not None \
                and 'run_ledger' not in result:
            result['run_ledger'] = {'path': str(getattr(self.store, 'path', '')),
                                    'run': self.run_id,
                                    'team': self.store.team_slot,
                                    'rotation': self.store.data['rotation']}
        result['steps'] = self.artifacts['steps']
        result['clicks_sent'] = self.artifacts['clicks_sent']
        result['verified_clear'] = self.artifacts['verified_clear']
        flow_records = self.artifacts['flow_steps']
        if self.artifacts['flow'] is not None:
            result['flow'] = self.artifacts['flow']
            result['flow_steps'] = flow_records
        result['foreground_after'] = _foreground(self.device)
        failed_flow = next((entry for entry in flow_records
                            if not (entry.get('passed')
                                    or entry.get('reason') == 'observe_only')), None)
        last = result['steps'][-1] if result['steps'] else None
        result['page_before'] = None if last is None else last['page_before']
        result['page_after'] = None if last is None else last.get('page_after')
        result['passed'] = (all(entry['passed'] for entry in result['steps'])
                            and bool(result['steps'] or flow_records)
                            and failed_flow is None)
        result['reason'] = ('window_steps_passed' if result['passed']
                            else ((failed_flow or {}).get('reason')
                                  or (last or {}).get('stopped')
                                  or (last or {}).get('reason')
                                  or 'no_step_recorded'))
        return result


def _foreground(device):
    if hasattr(device, 'foreground'):
        return device.foreground()
    return None


def _fresh_state(settings, store=None):
    """The per-window counters the loop carries; one dict, so a caller can resume."""
    wanted_plan = None
    try:
        wanted_plan = load_gift_plan(ROOT / str(settings.gift_plan))
    except (OSError, ValueError):
        wanted_plan = None
    grace_wanted = [int(part) for part in str(settings.graces).replace(' ', '').split(',')
                    if part.strip().isdigit()]
    map_points = []
    for part in str(settings.map_points or '').split(';'):
        pieces = [piece.strip() for piece in part.split(',') if piece.strip()]
        if len(pieces) == 2 and all(piece.isdigit() for piece in pieces):
            map_points.append((int(pieces[0]), int(pieces[1])))
    return {'step': 0, 'unknown_seen': 0, 'battle_sig': None, 'battle_rounds': 0,
            'map_progress': MapProgress(), 'floor_now': None, 'map_attempts': 0,
            'page_attempts': 0, 'gift_picks': 0, 'initial_picked': 0,
            'repeated_plans': {}, 'guard_page': None, 'claim_steps': 0,
            'team_slot_picked': None, 'defeat_row_sent': False, 'defeat_attempts': 0,
            'tutorial_cards': set(), 'grace_wanted': grace_wanted, 'grace_bought': set(),
            'gift_plan': wanted_plan, 'map_points': map_points,
            # Whether the run this window is paying out earned its payout: it starts
            # from the ledger (a window that begins on a claim still knows what it is
            # claiming) and every summary this window settles refreshes it.
            'run_settled_itself': bool(earned_its_payout(store))}


def _roots():
    return ROOT


def _load_registry():
    return json.loads(REGISTRY.read_text(encoding='utf-8'))


# --------------------------------------------------------------------------- helpers


def _settle(observer, before, before_sha, rounds, interval, deadline):
    """Read until the screen moves, at most ``rounds`` times: the window's own loop.

    The first observation is the frame the caller already has; a reading that is
    still the same picture is read again until ``rounds`` is spent. ``changed`` is
    the final reading compared with ``before_sha``: a frame with no hash at all is
    never called a change.
    """
    after = before
    for round_index in range(max(1, rounds)):
        if round_index:
            time.sleep(interval)
        after = observe(observer, deadline)
        if after.get('image_sha256') not in (None, before_sha):
            break
    changed = after.get('image_sha256') not in (None, before_sha)
    return after, changed


def one_shot_click(device, observer, box, *, label='one_shot_click', index=None,
                   deadline=None, journal=None, rounds=3, interval=4.0, preflight=None):
    """One diagnostic click on a named box, proved by the frame changing.

    The window's ``--click-box``. It is not part of the dungeon loop: it exists so a
    calibration point can be pressed and watched, and it never plans anything.
    """
    before = observe(observer, deadline)
    if preflight is not None:
        box = preflight(before)
    before_sha = before.get('image_sha256')
    box = [int(value) for value in box]
    inset = inset_box(tuple(box), .3)
    x, y, w, h = inset
    point = (random.randint(x, x + max(1, w)), random.randint(y, y + max(1, h)))
    delay = random.randint(350, 750)
    label = label if index is None else '%s[%d]' % (label, index)
    if journal is not None:
        journal.record('one_shot_intent', label=label, box=box, point=list(point),
                       delay_ms=delay)
    device.click(point[0], point[1])
    time.sleep(delay / 1000)
    after, changed = _settle(observer, before, before_sha, rounds, interval, deadline)
    return {'label': label, 'action': 'click', 'target': box,
            'click_point': list(point), 'delay_ms': delay,
            'page_before': before.get('scene'), 'page_after': after.get('scene'),
            'scene_before': before.get('scene'), 'scene_after': after.get('scene'),
            'observation': before, 'settled': after, 'passed': bool(changed),
            'reason': ('one_shot_screen_changed' if changed
                       else 'one_shot_screen_unchanged')}


def one_shot_swipe(device, observer, parts, *, label='one_shot_click', index=None,
                   deadline=None, journal=None, rounds=3, interval=4.0):
    """One diagnostic drag, proved by the frame changing (the window's ``--swipe``)."""
    before = observe(observer, deadline)
    before_sha = before.get('image_sha256')
    parts = [int(value) for value in parts]
    duration = parts[4] if len(parts) > 4 else 600
    label = '%s_swipe' % label if index is None else '%s_swipe[%d]' % (label, index)
    if journal is not None:
        journal.record('one_shot_intent', label=label, gesture='swipe',
                       points=list(parts), duration_ms=duration)
    device.swipe(parts[0], parts[1], parts[2], parts[3], duration)
    time.sleep(max(0.6, duration / 1000))
    after, changed = _settle(observer, before, before_sha, rounds, interval, deadline)
    return {'label': label, 'action': 'swipe', 'target': parts,
            'duration_ms': duration,
            'page_before': before.get('scene'), 'page_after': after.get('scene'),
            'scene_before': before.get('scene'), 'scene_after': after.get('scene'),
            'observation': before, 'settled': after, 'passed': bool(changed),
            'reason': ('one_shot_screen_changed' if changed
                       else 'one_shot_screen_unchanged')}


def observed_page(observer, registry, settings, *, journal=None, deadline=None):
    """The zero-input read the window's ``--observe-page`` prints."""
    record = observe(observer, deadline)
    page = resolve_scene(registry, observer.directory, record)
    frames = sorted(Path(observer.directory).glob('frame-*.png'))
    tokens = [[item['text'], list(item['box']), round(item['score'], 3)]
              for item in record.get('ocr') or []]
    return {'scene': record.get('scene'), 'page': page, 'size': record.get('size'),
            'floor': record.get('floor'), 'pack': record.get('pack'),
            'wave': record.get('wave'), 'turn': record.get('turn'),
            'start_box': record.get('start_box'),
            'auto_assign_buttons': record.get('auto_assign_buttons'),
            'sha256': record.get('image_sha256'),
            'frame': None if not frames else frames[-1].name, 'tokens': tokens}


def build_parser(defaults=None):
    """The window CLI's parser: its flags and its help text live here for both users."""
    defaults = defaults or _defaults()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--binary', type=Path, required=True,
                        help='MaaFramework build to load (the maafw development tree)')
    parser.add_argument('--adb', type=Path,
                        help='adb binary; MuMu\'s own adb is used when omitted')
    parser.add_argument('--input-method', help='pin the Maa input backend by name')
    parser.add_argument('--address', required=True, help='device serial, host:port')
    parser.add_argument('--authorize', required=True,
                        help='nonce granted by build/map-probe-authorization.json')
    parser.add_argument('--steps', type=int, default=defaults['steps'],
                        help='how many steps to walk (default: one)')
    parser.add_argument('--rounds', type=int, default=defaults['rounds'],
                        help='settle rounds after each input')
    parser.add_argument('--unknown-rounds', type=int, default=defaults['unknown_rounds'],
                        help='how many turns an unreadable page may hold the run '
                             '(default: 30)')
    parser.add_argument('--battle-rounds', type=int, default=defaults['battle_rounds'],
                        help='how many turns a battle may repeat one readout')
    parser.add_argument('--interval', type=float, default=defaults['interval'],
                        help='seconds between observations')
    parser.add_argument('--map-tries', type=int, default=defaults['map_tries'],
                        help='how many map spots may be tried before stopping')
    parser.add_argument('--page-tries', type=int, default=defaults['page_tries'],
                        help='how many times a missing reading may be retried')
    parser.add_argument('--map-points', default=defaults['map_points'],
                        help='calibration points as x,y;x,y (1280-space)')
    parser.add_argument('--team', type=int, default=defaults['team'],
                        help='which saved team slot to bring')
    parser.add_argument('--run-store', type=Path, default=defaults['run_store'],
                        help='run ledger; its rotation decides the team slot')
    parser.add_argument('--graces', default=defaults['graces'],
                        help='which star-grace card indexes may be bought')
    parser.add_argument('--grace-budget', type=int, default=defaults['grace_budget'],
                        help='starlight budget when the page does not print one')
    parser.add_argument('--gift-keyword', default=defaults['gift_keyword'],
                        help='the E.G.O gift keyword the rotation wants')
    parser.add_argument('--gift-plan', default=defaults['gift_plan'],
                        help='gift plan file naming the keyword\'s wanted gifts')
    parser.add_argument('--gift-search', choices=('refuse', 'select'),
                        default=defaults['gift_search'],
                        help='what to do on the gift-search page')
    parser.add_argument('--loop-guard', type=int, default=defaults['loop_guard'],
                        help='how many times one plan may repeat before stopping')
    parser.add_argument('--claim-tries', type=int, default=defaults['claim_tries'],
                        help='how many claim steps may repeat across the family')
    parser.add_argument('--observe-page', action='store_true',
                        default=defaults['observe_page'],
                        help='read one page, print it and send nothing')
    parser.add_argument('--observe-only', action='store_true',
                        default=defaults['observe_only'],
                        help='walk the pages but send no input at all')
    parser.add_argument('--defeat-tries', type=int, default=defaults['defeat_tries'],
                        help='how many wipes may be retried before accepting')
    parser.add_argument('--defeat-accept', action='store_true',
                        default=defaults['defeat_accept'],
                        help='accept the wipe instead of retrying it')
    parser.add_argument('--stop-page', default=defaults['stop_page'],
                        help='hand control back the moment this page shows')
    parser.add_argument('--click-box', action='append', default=defaults['click_box'],
                        help='one diagnostic click as x,y,w,h')
    parser.add_argument('--swipe', action='append', default=defaults['swipe'],
                        help='one diagnostic swipe as x1,y1,x2,y2[,duration_ms]')
    parser.add_argument('--flow', default=defaults['flow'],
                        help='named session flow to walk before the loop')
    parser.add_argument('--after-flow', action='store_true',
                        default=defaults['after_flow'],
                        help='walk the dungeon loop after the flow')
    parser.add_argument('--flow-list', action='store_true',
                        help='print every flow step and exit')
    parser.add_argument('--label', default=defaults['label'],
                        help='label for --click-box/--swipe records')
    parser.add_argument('--report', type=Path, default=defaults['report'],
                        help='also write the summary JSON here')
    return parser
