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
import threading
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

import cv2

from . import session_flow as flows
from .anchor import ANCHOR_MISSING, reread_allowed
from . import map_dispatch
from .pages import REFUSALS, kind_of, ladder_for, recovery_for, superseded_click
from .anchors import evaluate
from .event_vision import (best_check_choice, check_box, check_stage, choice_options,
                           gift_hints, odds_scores, preferred_choice)
from .floor_gift_transaction import RECEIPT_SUCCESSOR_PAGES
from .gift_plan import load as load_gift_plan, wanted as wanted_gifts
from .grace_vision import available_starlight, cost_of, plan_purchases, plus_points
from .jobs import bounded_limit, dispatch, screencap, wait_job, wait_task
from .map_progress import MapProgress
from . import map_vision
from .map_vision import (NODE_BADGE_TEMPLATE, adjacent_to, map_clicks, map_header,
                         party_point, gold_marks, movement_between)
from .overlay_vision import carousel_dots, page_turn_arrows
from .reward_vision import (GIFT_COUNTER_BAND, INITIAL_COUNTER_BAND, counter_state,
                            gift_cards, initial_gift_box, keyword_panel_point,
                            select_ready)
from .run_wiring import earned_its_payout, expire, reconcile, settle
from .shop_vision import currency as shop_currency, offers as shop_offers
from .shop_vision import (SHELF_PRICE_FAINT_FLOOR, SHELF_PRICE_FLOOR, shelf_tokens,
                          wanted_offers)
from .shop_settings import CARRY_CAP_COINS
from .team_vision import CARD_COUNT, assignment_numbers, card_states, participants
from .vision import Text, inset_box
from . import click_trace
from .window import (ANY, CLICK, NODE, SWIPE, WAIT_PAGES, plan_step, resolve_overlay,
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
    'MirrorDrive': {
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
        # A *complete* run is five verified floors, a claimed payout and a return to the
        # lobby; ``steps``/``rounds`` bound one window and never count runs. Zero means the
        # player did not name a number and the window walks until another bound stops it.
        'run_count': 0,
        'interval': 4.0, 'map_tries': 8, 'page_tries': 3, 'team': 5,
        # A wedged recognition never returns, so the loop is watched from outside it:
        # with no new frame for this many seconds the process ends itself loudly
        # instead of sitting silent (live run pi-20261015-191205, 19:16:07).
        'stall_seconds': 300.0,
        # How many viewport gestures a step that did not land may spend before the run
        # ends. The default is the whole ladder; zero leaves the whole mechanism off.
        'recovery_tries': len(RECOVERY_LADDER),
        'gift_keyword': 'bleed', 'gift_plan': 'assets/resource/base/gift-plan.json',
        'gift_search': 'refuse', 'shop_refreshes': 2,
        'shop_policy': 'manual', 'shop_reserve_coins': 500,
        'shop_carry_cap_coins': CARRY_CAP_COINS,
        'battle_assignment':'win_rate', 'loop_guard': 3, 'claim_tries': 6,
        'observe_only': False, 'stop_page': None, 'grace_budget': 60, 'grace_auto': False,
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
        if (self._values['shop_policy'] not in ('manual','learned') or
                type(self._values['shop_refreshes']) is not int or not 0<=self._values['shop_refreshes']<=5 or
                type(self._values['shop_reserve_coins']) is not int or not 0<=self._values['shop_reserve_coins']<=500 or
                type(self._values['shop_carry_cap_coins']) is not int or not 0<=self._values['shop_carry_cap_coins']<=3000):
            raise ValueError('Invalid bounded shop settings')
        if type(self._values['run_count']) is not int or not 0 <= self._values['run_count'] <= 50:
            raise ValueError('Invalid bounded mirror run count')

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


def granted_nonce():
    """The nonce the live-input gate currently grants, or ``None``.

    A refusal that only says "a grant is required" costs a round: the driver printed
    that and the operator had to go read the file.  The gate already knows the answer,
    so it says it.
    """
    if not AUTHORIZATION.is_file():
        return None
    try:
        data = json.loads(AUTHORIZATION.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if data.get('live_input_authorized') is not True:
        return None
    nonce = data.get('nonce')
    return nonce if isinstance(nonce, str) and nonce else None


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

    def pinch(self, centre, radius, factor, seconds=0.9) -> None:
        """Close two simulated fingers towards each other; taps nothing."""


MAP_ZOOM_OUT = {'centre': (960, 540), 'radius': 320, 'factor': 0.55, 'seconds': 0.9}
"""The calibrated map pinch-out, in the 1920x1080 recognition space.

``tools/map_zoom.py`` proved this gesture on the live game and the runner sends the
same vector; the tool's one-off nonce is not needed here, because the runner is
already the authorized driver of the run it is pinching for.
"""

RECOVERY_DRAG = (960, 380, 960, 760)
"""The vertical drag a recovery gesture uses, in the same 1920x1080 space."""

_TARGET_LONG_SIDE = int(os.environ.get('MAALIMBUS_TARGET_LONG_SIDE', 1920))

RECOVERY_PAN = (620, 540, 1300, 540)
"""The horizontal pan a recovery gesture uses, in the same 1920x1080 space.

A Mirror Dungeon floor is wider than the viewport: dragging it changed 29272 px on
the live client of 2026-10-22 (``build/t100-swipe-700.png`` versus ``build/t100-s0.png``)
and carried nodes into view that no earlier frame had contained, while the party
stayed where it was.  ``RECOVERY_LADDER`` had drags in one axis only, so a floor whose
last two steps sat off screen looked exactly like a floor with nowhere to go --
which is the shape every stop of that session took.
"""

MAP_PROGRESS_CONTROL = (1780, 8, 128, 104)   # the map page's progress button, agent space
FIXED_LAYOUT_PAGES = ('HOME', 'DRIVE', 'THEME', 'REWARD', 'EXPLORATION_COMPLETE')
"""Pages whose layout does not scroll or zoom, so viewport gestures are not recoveries."""

SUBMIT_IGNORED_WINDOW_S = 25.0
SUBMIT_IGNORED_ATTEMPTS = 3


COL_STEP = 190.0   # lattice pitch across a column, measured within single frames
ROW_STEP = 176.0   # pitch between rows; adjacent rows are offset by half a column


def one_step_from(point, cell, *, col=COL_STEP, row=ROW_STEP, slack=0.30):
    """True when `point` is one lattice step from `cell`.

    The floor is a hex lattice.  The pitches are measured, not inferred: taking every
    pair of gold marks inside single frames of
    `evidence/runtime/packaged-mirror-20261022-063646` (298 marks, 120 frames) the
    difference histogram peaks at dx 190 and 100 (half a column) and dy 0 and 180, so a
    walkable neighbour is either the same row one column away or the adjacent row half a
    column away.  Positions must never be taken modulo anything: the map pans, so the
    lattice has no frame-independent origin.
    """
    dx = abs(float(point[0]) - float(cell[0]))
    dy = abs(float(point[1]) - float(cell[1]))
    same_row = dy <= slack * row and abs(dx - col) <= slack * col
    diagonal = abs(dx - col / 2) <= slack * col and abs(dy - row) <= slack * row
    return bool(same_row or diagonal)


# The party can stand against the header: on a fresh floor 1 the torch sits at y about
# 67 of 1080 (build/ob0.png), so a 0.10 top edge excluded the very thing this guard is
# meant to keep and made `party_point` answer None on a page where the dot was visible.
BOARD = (0.0, 0.02, 0.80, 0.88)   # the map is drawn inside these frame fractions


def party_point(image, *, board=BOARD):
    """The party dot, or None when the reading is not on the board.

    `player_of` picks the yellow blob with the most flame under it, and the header and
    the right-hand panel also carry yellow: on
    `evidence/runtime/packaged-mirror-20261022-063646` frames 0023..0027 read (694,384)
    and 0028..0032 read (1616,82), a 922 px jump into the HUD.  Anything outside the
    board is not the party.
    """
    # `map_vision.party_point` is the reading this repo maintains (torch specks, all-pairs
    # search, scale-free thresholds); this module's own definition used to shadow it, so
    # every fix made there never ran and the live loop answered None where the离线 reading
    # of the same PNG answers a point -- evidence/runtime/packaged-mirror-20261023-045452/
    # frame-0020.png: map_vision (1628,561) vs runner None, and candidates_of 0 vs 5.
    try:
        fresh = map_vision.party_point(image)
    except (AttributeError, TypeError, ValueError):
        fresh = None
    if fresh:
        return fresh
    try:
        point = map_vision.player_of(image, [])
    except (AttributeError, TypeError, ValueError):
        return None
    if not point:
        return None
    height, width = image.shape[:2]
    left, top, right, bottom = board
    x, y = float(point[0]), float(point[1])
    if not (left * width <= x <= right * width and top * height <= y <= bottom * height):
        return None
    return point


def next_untried(candidates, tried):
    """Index of the first map candidate this page has not already been asked about.

    The map used to click ``candidates[0]`` for ever: `choice_index` starts at 0 and only
    event pages ever moved it, so a rejected node was retried until the page budget ran
    out instead of trying the next one.  Several nodes are usually offered at once (live
    build/t94-now.png has four), and the user's own reading of it is the right one -- try
    the next destination rather than dying on the first.  ``tried`` holds the boxes this
    page already received a click at, and is emptied by the caller when the page changes,
    so a floor that has advanced starts from the best-ranked node again.
    """
    if not candidates:
        return 0
    def box_of(candidate):
        raw = candidate['box'] if isinstance(candidate, dict) else candidate
        return tuple(int(v) for v in raw)

    seen = {tuple(int(v) for v in box) for box in tried or ()}
    for index, candidate in enumerate(candidates):
        if box_of(candidate) not in seen:
            return index
    return 0


def submit_was_ignored(previous_turn, turn, elapsed, *, window=SUBMIT_IGNORED_WINDOW_S):
    """True when a second submit is about to be sent from the turn the first one left.

    The page name cannot answer this: the submit plan expects BATTLE_HUD, BATTLE_PLANNING
    and UNKNOWN, so a board that ignored the click looks exactly like one that accepted it.
    The HUD's own turn counter is read every frame and is the only fact that separates
    them; 25 s is well under the measured 43 s a real turn takes.
    """
    if previous_turn is None or turn is None:
        return False
    return str(turn).strip() == str(previous_turn).strip() and float(elapsed) > float(window)


DEEP_STEP_SECONDS = 60.0
RECOVERY_LADDER = (
    ('pinch_out', 'the_view_is_pinched_out_so_the_page_shows_all_of_itself'),
    ('drag_down', 'the_page_is_dragged_back_towards_its_first_rows'),
    ('drag_up', 'the_page_is_dragged_on_towards_its_later_rows'),
    ('pan_left', 'the_page_is_wider_than_the_viewport_and_is_panned_back_towards_its_start'),
    ('pan_right', 'the_page_is_wider_than_the_viewport_and_is_panned_on_towards_its_end'),
    ('wait', 'the_page_is_given_one_more_round_to_settle'),
)
"""What a step that did not land gets before the run is allowed to end.

Every rung moves the viewport and presses no game control, so the ladder is safe on
a page whose layout the reader does not know yet. ``_recover`` spends one rung per
stop, and the run ends only once the ladder is spent for that stop.
"""


def map_stop_reason(*, tried, attempts):
    """Which map failure happened: nothing to read, or nothing accepted.

    A frame with no candidate means the reader missed a node and waiting is the
    cure. A floor that refused every click it was given means the page itself
    would not step -- live ``evidence/runtime/packaged-mirror-20261021-202503``
    sent seven inputs to ringed, chevron-marked and ``?`` nodes that all left the
    page identical while the gear button moved 228 435 pixels -- and calling that
    `no_candidate_node_observed` sends the next run after the reader instead.
    """
    return ('map_clicks_had_no_effect' if tried and attempts
            else 'map_candidates_not_observed_yet')


def pinch_out(controller, wait, *, centre=MAP_ZOOM_OUT['centre'],
              radius=MAP_ZOOM_OUT['radius'], factor=MAP_ZOOM_OUT['factor'],
              seconds=MAP_ZOOM_OUT['seconds'], steps=12):
    """Close two simulated fingers towards each other until the view zooms out.

    Nothing is clicked: the emulator sees two touch points (ids 0 and 1) go down at
    ``centre`` +/- ``radius`` and walk in to +/- ``radius * factor``, which is what
    the game reads as "zoom out". A controller without touch simulation raises
    :class:`NotImplementedError` instead of falling back to a click on the map.
    """
    if getattr(controller, 'post_touch_down', None) is None or getattr(controller, 'post_touch_move', None) is None:
        raise NotImplementedError('this controller cannot simulate two fingers')
    cx, cy = (int(value) for value in centre)
    reach = max(1, int(radius))
    target = max(1, int(reach * float(factor)))
    steps = max(1, int(steps))
    wait(controller.post_touch_down(cx - reach, cy, 0), timeout=10)
    wait(controller.post_touch_down(cx + reach, cy, 1), timeout=10)
    for index in range(1, steps + 1):
        offset = reach - (reach - target) * index / steps
        wait(controller.post_touch_move(int(cx - offset), cy, 0), timeout=10)
        wait(controller.post_touch_move(int(cx + offset), cy, 1), timeout=10)
        time.sleep(float(seconds) / steps)
    wait(controller.post_touch_up(0), timeout=10)
    wait(controller.post_touch_up(1), timeout=10)


def stall_watchdog(heartbeat_of, *, limit, on_stall, every=5.0, rounds=None,
                   probe=None, sleep=time.sleep, exit=os._exit):
    """End a process that has stopped producing frames.

    ``heartbeat_of`` returns the monotonic stamp of the newest frame. A recognition
    call that never returns cannot be recovered by any gesture -- live run
    pi-20261015-191205 wedged in one at 19:16:07 and sat silent for twelve minutes
    with no frame, no event and no result -- so the loop is watched from outside it
    and the process ends itself loudly rather than hanging. ``rounds`` bounds the
    watch so a test can run it without arranging a real hang.
    """
    from . import stillness as _stillness
    looked = 0
    grace = 0
    while rounds is None or looked < rounds:
        sleep(every)
        looked += 1
        if time.monotonic() - float(heartbeat_of()) > limit * (1 + grace):
            # One bounded re-read is the only honest source for `probe_changed`: a
            # static screen that still answers a re-read is alive, one that answers
            # nothing is frozen.  Without a probe the answer stays `None`, which the
            # classifier treats as "no evidence", never as "dead".
            changed = probe() if probe is not None else None
            try:
                record = on_stall(probe_changed=changed) or {}
            except TypeError:
                record = on_stall() or {}
            verdict = _stillness.should_exit(
                action=record.get('stillness_action', _stillness.STOP),
                grace_used=grace)
            if not verdict['exit']:
                # A static interstitial or an alive page buys one more window; the
                # bound is explicit so a real wedge still ends the process.
                grace = verdict['grace_used']
                continue
            exit(4)
    return looked


class MaaDevice:
    """A :class:`Device` over a MaaFramework controller.

    ``controller`` is ``context.tasker.controller`` in an agent custom action, so
    this never builds a controller of its own and never needs one: the loop's input
    goes out through the task the agent already owns. Every call posts its job,
    waits it out under a deadline and only then returns, which is what makes
    ``click()`` mean "the touch landed" rather than "the touch was queued".
    """

    def __init__(self, controller, *, wait=None, target_long_side=None, deadline=None, tasker=None):
        self.controller = controller
        self.tasker = tasker
        self.ended = None
        self.wait = wait
        self.deadline = deadline
        # None means "the configured default"; 0 means "ask the controller for nothing".
        self.target_long_side = _TARGET_LONG_SIDE if target_long_side is None else target_long_side
        if self.target_long_side:
            controller.set_screenshot_target_long_side(int(self.target_long_side))

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

    def end_session(self, reason):
        """Name why this device may never post input again.

        Maa tears a task down when one of its pipeline nodes fails, and the
        controller behind it is freed with the task.  A click posted afterwards
        reads through a released pointer, which is a native access violation the
        interpreter cannot catch, so the death has to be recorded here first.
        """
        if self.ended is None:
            self.ended = str(reason)

    def _refuse_if_ended(self, what):
        if self.ended is not None:
            raise RuntimeError('the session ended (%s); refusing to post a %s'
                               % (self.ended, what))

    def click(self, x, y):
        self._refuse_if_ended('click')
        self._wait(self.controller.post_click(int(x), int(y)))

    def swipe(self, x1, y1, x2, y2, duration_ms):
        self._refuse_if_ended('swipe')
        self._wait(self.controller.post_swipe(int(x1), int(y1), int(x2), int(y2),
                                              int(duration_ms)), timeout=15)

    def key(self, code):
        post = getattr(self.controller, 'post_key', None)
        if post is None:
            raise NotImplementedError('this controller has no key input')
        self._wait(post(int(code)))

    def pinch(self, centre, radius, factor, seconds=0.9):
        """Pinch the view out with the calibrated two-finger vector.

        The runner reaches for this when the map refuses to move: the same gesture
        ``tools/map_zoom.py`` sent when it was calibrated on the live game.
        """
        pinch_out(self.controller, self._wait, centre=centre, radius=radius,
                  factor=factor, seconds=seconds)


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

    def pinch(self, centre, radius, factor, seconds=0.9):
        """Pinch the view out with the calibrated two-finger vector.

        The runner reaches for this when the map refuses to move: the same gesture
        ``tools/map_zoom.py`` sent when it was calibrated on the live game.
        """
        pinch_out(self.controller, self._wait, centre=centre, radius=radius,
                  factor=factor, seconds=seconds)

    def foreground(self):
        """The foreground window of the ADB device, or ``None`` when unknown."""
        if self.device is None:
            return None
        from .adb_device import foreground_of
        return foreground_of(self.device)


def local_device(controller, device=None, tasker=None, *, deadline=None, wait=None,
                 target_long_side=None):
    """Build the ADB-side device the window has always driven.

    ``MAALIMBUS_TARGET_LONG_SIDE`` overrides the 1920 upscale for every run: the frame
    the loop reads and the pixels maafw clicks have to agree, and 1280 keeps the frame
    at the device's own size.  That is the one-variable experiment for whether a click
    is scaled back before it reaches the device (the live runs of 2026-10-22 sent
    clicks that changed not one pixel inside the target box).
    """
    return LocalDevice(controller, device=device, tasker=tasker, deadline=deadline,
                       wait=wait, target_long_side=target_long_side or _TARGET_LONG_SIDE)


class FakeDevice:
    """A :class:`Device` for tests: replays frames and remembers what was sent."""

    def __init__(self, frames=(), foreground=None):
        self.frames = list(frames)
        self.clicks = []
        self.swipes = []
        self.keys = []
        self.pinches = []
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

    def pinch(self, centre, radius, factor, seconds=0.9):
        self.pinches.append((tuple(int(value) for value in centre), int(radius),
                             float(factor), float(seconds)))

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
                 battle_pipeline='WindowBattleObserve', read_tries=2):
        self.context = context
        self.directory = Path(directory if directory is not None
                              else getattr(context, 'directory', '.'))
        self.pipeline = pipeline
        self.battle_pipeline = battle_pipeline
        self.read_tries = read_tries

    @property
    def tasker(self):
        """The tasker whose pipeline nodes are run (a runner or a context has one)."""
        return getattr(self.context, 'tasker', None)

    def observe(self, *, deadline=None):
        """This frame's page, never the previous frame's event.

        A node whose own screencap fails records nothing and still returns a finished
        job, so a reader that only takes the newest event of its kind hands back the
        page from the *previous* frame. The packaged agent stopped a live run exactly
        that way: evidence/runtime/packaged-mirror-20261012-032032 has one
        ``map_observed`` in the whole run while the click it had sent was already on
        the board, and the deployment successor was then judged against the pre-click
        counter. A node that records nothing is re-run, and one that never records
        stops the run with that as the reason instead of a page it did not read.
        """
        recorded = events(self.directory, 'map_observed')
        before = len(recorded)
        for attempt in range(max(1, self.read_tries)):
            run_node(self.tasker, self.pipeline, deadline)
            recorded = events(self.directory, 'map_observed')
            if len(recorded) > before:
                break
        if len(recorded) <= before:
            raise RuntimeError('the observation node recorded no page for this frame')
        record = recorded[-1]
        if record.get('scene') in BATTLE_PAGES:
            battle = events(self.directory, 'battle_observed')
            before_battle = len(battle)
            for attempt in range(max(1, self.read_tries)):
                run_node(self.tasker, self.battle_pipeline, deadline)
                battle = events(self.directory, 'battle_observed')
                if len(battle) > before_battle:
                    break
            if len(battle) <= before_battle:
                raise RuntimeError('the battle observation node recorded no page for this frame')
            record = battle[-1]
        return record


def observe(observer, deadline=None):
    """Read the live page once and return its journal record.

    The analyze event itself carries no frame hash, tokens or size, so they are
    attached here: the repeated-card guard, the "did the click move the screen"
    check, the guide-book carousel and the pre-battle team reader all need them.

    The native local reads are attached for the same reason. ``MaaObserver``
    answers with the semantic ``map_observed`` event, so a live pre-battle page
    reached :func:`team_state` without the ``deployment_availability`` record the
    frame the same step had just written carried: the run then read an 11-card
    capacity with no unavailable card, spent both re-reads, and stopped on
    ``Current deployment capacity requires independent unavailable-card proof``
    (evidence/runtime/window-20261012-202916/frame-0003.json holds the accepted
    proof, ``unavailable: [6]``). Replayed frames keep working: a frame record
    already carries its own local reads, and only a missing list is filled in.
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
        local = details.get('local_ocr')
        if local and not record.get('local_ocr'):
            record['local_ocr'] = local
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


def header_chrome(record):
    """The floor caption and pack line of a MAP page, as boxes no node can occupy.

    The top left of the map page carries the page's own chrome over the artwork, and
    lit glyphs under it come back as nodes (live window-20261012-022147/frame-0021.json:
    a ``lit_icon`` at (278,132,40,40) whose centre sits inside the ``Exploring Floor 1``
    caption). A real node never overlaps those captions.
    """
    if record.get('scene') != 'MAP':
        return []
    texts = [Text(item['text'], tuple(item['box']), item['score'])
             for item in record.get('ocr') or ()]
    header = map_header(texts, record.get('size') or (1920, 1080))
    if header is None:
        return []
    boxes = [list(header.exploring_text.box)]
    if header.pack_text is not None:
        boxes.append(list(header.pack_text.box))
    # Caption digits blink and OCR may split Exploring/Floor. Reserve the
    # visible header panel even when the last glyph's OCR box disappears.
    width,height=record.get('size') or (1920,1080)
    boxes.append([round(width*.02),round(height*.105),round(width*.28),round(height*.105)])
    return boxes


def inside_chrome(box, chrome):
    """True when a candidate box's centre falls inside one of ``chrome``'s boxes."""
    centre = (box[0] + box[2] / 2, box[1] + box[3] / 2)
    return any(item[0] <= centre[0] <= item[0] + item[2]
               and item[1] <= centre[1] <= item[1] + item[3] for item in chrome)



CONTROLS = ('enter', 'battle', 'start', 'confirm', 'cancel', 'select', 'proceed', 'refresh',
            'leave', 'continue', 'accept', 'refuse', 'close', 'next', 'skip', 'claim', 'to window')


def looks_like_transition(record):
    """Is this frame an animation rather than a page the loop should answer?

    A transition is *empty of meaning*: a few fragmentary reads (damage numbers, half a
    word from a cutscene caption) and not one control.  A page this reader does not know
    yet still prints its buttons, so it stays a page and keeps the unknown budget.
    """
    texts = [str(t.get('text') or '') for t in (record.get('ocr') or [])]
    words = [t for t in texts if any(ch.isalpha() for ch in t)]
    if len(words) > 6 or len(texts) > 24:
        return False
    lowered = ' '.join(texts).lower()
    return not any(control in lowered for control in CONTROLS)


def overlaps(box, other):
    """True when two boxes share any area (used to drop page chrome from the map list)."""
    x, y, w, h = (float(v) for v in box)
    ox, oy, ow, oh = (float(v) for v in other)
    return x < ox + ow and ox < x + w and y < oy + oh and oy < y + h


def candidates_of(directory, record):
    """Ordered click boxes for a MAP page, the step the game marks first.

    Which nodes the run may step to depends on the paths drawn under the dots, and
    that connectivity is not readable from a frame, so the list is ordered and only the
    page's own chrome is dropped: the window tries the rest in turn and stops at the
    first that really opens the panel, and a click on an unreachable node is a harmless
    no-op. The order comes from map_vision.map_clicks: the desaturated-bright glyph the
    game uses to mark the step it will accept, then the crescent-badge nodes away from
    the player.
    """
    if record['scene'] != 'MAP':
        return None, None
    image, name = latest_frame(directory)
    if image is None:
        return None, None
    clicks = map_clicks(image, template=node_badge_template())
    chrome = header_chrome(record)
    if chrome:
        clicks = [item for item in clicks if not inside_chrome(item['box'], chrome)]
    # The map page's own progress button is warm and framed like a node, so it was offered
    # as a destination -- and because opening it dims the board, the party reading moved and
    # the click was booked `accepted` (evidence/runtime/packaged-mirror-20261023-050219:
    # the only two acceptances are target=[1780,8,128,104], the progress button, while all
    # six real nodes came back `rejected`).  A control is never a destination.
    clicks = [item for item in clicks if not overlaps(item['box'], MAP_PROGRESS_CONTROL)]
    # Only a node one step from the party can move it.  Without this filter the list
    # was ordered but unconstrained, so runs kept clicking nodes two or more steps out
    # and every verdict came back `rejected` while the party stood still
    # (evidence/runtime/packaged-mirror-20261022-085428: party (1052,562), targets from
    # (576,361) outward).  If the party cannot be read the list is left whole, because
    # an unread party must not leave the run with nothing to try.
    party = party_point(image)
    # The verdict that follows this click must carry the same party the candidates
    # were filtered against; nothing else records it (see `_map_verdict`).
    record['map_party'] = list(party) if party else None
    boxes = [list(item['box']) for item in clicks]
    if party is None:
        # No party, no adjacency, no click.  Every frame of
        # `evidence/runtime/packaged-mirror-20261022-090550` read None while the board
        # band stopped short of where the party stood, and the "unread party filters
        # nothing" fallback then let the loop spend six clicks on nodes two steps away.
        # A frame that cannot say where the party is must say so, not guess.
        return name, []
    return name, adjacent_to(party, boxes)


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
    availability=next((p for p in record.get('local_ocr',[]) if p.get('purpose')=='deployment_availability'
                       and p.get('accepted')),None)
    return {'availability':availability,'unavailable':list((availability or {}).get('unavailable',[])),
            'states': card_states(records, boxes, size),
            'participants': participants(records, size),
            'numbers': assignment_numbers(records, boxes, size)}


def pre_battle_identity_evidence(directory, record, saved_order=(), order_badges=()):
    """The twelve grid slots' identity reading for one real pre-battle frame.

    Presence is measured from the frame's own pixels, so a grid slot whose card
    border was not found is reported missing rather than assumed occupied. The
    reading comes from the caption and emblem teachers only: no detector is read
    here, and nothing here sends input. Returns ``None`` when this frame is not
    the pinned 1920x1080 team screen, because the card grid is only proven there.

    ``saved_order`` is the rotation's own position order and ``order_badges`` the
    per-slot printed deployment numbers; the order verdict is only reported when
    the caller really measured those badges, since the grid position alone does
    not say which deployment position a card occupies.
    """
    from . import pre_battle_identity as teacher
    from .neural_shadow import measured_card_border
    from .storage import read_json
    if record.get('scene') != 'PRE_BATTLE_TEAM' or list(record.get('size') or []) != [1920, 1080]:
        return None
    image, name = latest_frame(directory)
    if image is None or list(image.shape[:2]) != [1080, 1920]:
        return None
    # The reading must be about the frame in hand, not about whatever the newest
    # stored pixels happen to be: a frame the observer has already moved past would
    # otherwise be reported under this record's evidence.
    if hashlib.sha256((Path(directory)/name).read_bytes()).hexdigest() != record.get('image_sha256'):
        return None
    present = [slot for slot in range(teacher.SLOTS)
               if measured_card_border(image, teacher.card_box(slot)) is not None]
    index = read_json(ROOT / 'assets/resource/base/identity-index.json')
    report = teacher.identity_report(record.get('ocr') or [], present_slots=present,
                                     pixels=image, aliases=teacher.alias_index(index))
    fields = dict(frame=name, schema_version=report['schema_version'],
                  teacher=report['teacher'], detector_read=report['detector_read'],
                  slot_count=report['slot_count'], slot_states=report['slot_states'],
                  measured_slots=report['measured_slots'],
                  missing_slots=report['missing_slots'],
                  resolved=[dict(grid_slot=row['grid_slot'], caption=row['caption'],
                                 identity_id=row['resolution'].get('identity_id'),
                                 sinner=row['resolution'].get('sinner'))
                            for row in report['slots']
                            if row['resolution'].get('resolved') is True],
                  unresolved=[dict(grid_slot=row['grid_slot'], caption=row['caption'],
                                   reason=row['resolution'].get('reason'),
                                   slot_state=row['slot_state'],
                                   badge_reason=row.get('badge_reason'))
                              for row in report['slots']
                              if row['resolution'].get('resolved') is not True],
                  unresolved_reasons=report['unresolved_reasons'], input_sent=False)
    order = [value for value in saved_order if type(value) is int]
    if len(order) == teacher.SLOTS:
        fields['saved_order'] = order
        team_verdict = teacher.agrees_with_saved_team(report, order)
        fields['verified_against_saved_team'] = team_verdict['verified']
        fields['saved_but_not_read'] = team_verdict['saved_but_not_read']
        fields['read_but_not_saved'] = team_verdict['read_but_not_saved']
        badges = list(order_badges) if len(list(order_badges)) == teacher.SLOTS else []
        if badges:
            order_verdict = teacher.agrees_with_saved_order(report, order, badges)
            fields['order_badges'] = badges
            fields['verified_against_saved_order'] = order_verdict['verified']
            fields['mismatched'] = order_verdict['mismatched']
            fields['unaligned_slots'] = order_verdict['unaligned_slots']
    return fields


def shop_state(record, wanted=(), bought=(), refreshes_used=0, refresh_limit=2,
               reserve_coins=0, policy='manual', learning=None, value_context=None,
               blocked=(), carry_cap_coins=None, gift_names=()):
    """What the shop page offers and the one input a shop visit may spend.

    A shop is spent from by reading its own page: every offer prints its name and
    its price, so the target is the card the page printed rather than a coordinate
    somebody guessed.  The answer carries, in the order a plan may use them:

    * ``confirm`` -- the Confirm of the shop's own purchase dialog, when one is up,
    * ``buy`` -- the first offer the gift plan asked for that the shop's currency
      covers, and which this run has not already paid for; its ``why`` says which rule
      chose it,
    * ``refresh`` -- the plain Refresh button, while a shop visit still has refreshes
      left and the currency covers one twice over (a refresh must never be able to
      eat the price of a gift the plan wants),
    * ``reason`` -- why none of the above is offered.

    The visit's carry cap comes last, and only when the visit has nothing better to do
    with its coins: when the gift plan has no affordable offer, no refresh is left worth
    taking, and the visit would still walk out with more than ``carry_cap_coins``, the
    surplus is spent on the cheapest offer the shelf itself prints that the player has
    not blocked and no earlier visit already bought (``why='carry_cap'``).  A run that
    leaves a shop with thousands of coins has bought nothing with them (the operator's
    directive of 2026-10-12: keep 500, at most 1500), and the purchase still has to prove
    itself against the shop's own printed price, exactly like the plan's own offers.
    ``carry_cap_coins=None`` disables that rule, and ``blocked`` names offers the player
    forbade: neither the plan nor the cap may buy one.  ``gift_names`` is the gift
    catalog's own vocabulary, and when it is supplied the cap only spends on an offer it
    names: the shelf also sells skill-replacement services, and buying one opens a
    chooser the shop's own purchase question never appears in.
    """
    if record.get('scene') not in ('SHOP', 'SHOP_PURCHASE') or not record.get('ocr'):
        return None
    from .shop_vision import purchase_confirm_target, refreshes as shop_refreshes
    size = record.get('size') or (1920, 1080)
    records = [Text(item['text'], tuple(item['box']), item['score'])
               for item in record['ocr'] if item['score']>=.9]
    # The shelf's own price badge is read below the currency's floor, so a six-slot
    # shelf whose badge OCRs at .835 is still six offers instead of four -- an
    # unchanged shelf must never pass for a refreshed one.  A badge can read fainter
    # still (frame-0149 of window-20261012-203743 printed a real badge at .763), so the
    # shelf keeps every token ``shelf_tokens`` will price; that reader is the one place
    # that decides a faint number is a badge.  A faint title is still not a title, and
    # the currency and refresh costs keep the stricter records, so a low-confidence
    # number can never price a refresh.
    shelf_read = [Text(item['text'], tuple(item['box']), item['score'])
                  for item in record['ocr'] if item['score']>=SHELF_PRICE_FAINT_FLOOR]
    question = record.get('scene') == 'SHOP_PURCHASE'
    found = shop_offers(shelf_tokens(shelf_read), size)
    cash = shop_currency(records, size)
    wanted_offers_now = wanted_offers(found, wanted, bought)
    buy = None
    refresh = None
    # On the shop's own purchase question the only readable input is its own Confirm:
    # buying, refreshing or leaving behind it would spend or cancel a purchase nobody
    # asked for, so no other answer is offered there.  The modal's own Purchase button
    # is a *scene* anchor and never an authorization: on this page the runner's
    # SHOP_PURCHASE branch may only hand a confirm over when the account proves it
    # (a reserved gift at its price on the currency the intent was written against).
    # The live 21:24:38 run died here -- a resumed 159-coin reservation met a dialog
    # whose own badge asked 390, the scene's button was planned anyway, and the
    # transaction layer refused it, ending the whole run.
    readable = purchase_confirm_target(records, size, require_offers=not question)
    confirm = None if question else readable
    if question:
        reason = ('the_shop_asked_about_a_purchase_and_its_confirm_is_the_only_input'
                  if readable else
                  'the_shop_asked_about_a_purchase_and_its_confirm_was_not_read')
        return {'currency': cash, 'buy': None, 'refresh': None, 'confirm': confirm,
                'reason': reason, 'wanted': list(wanted),
                'offers': [{'index': offer.index, 'name': offer.name,
                            'price': offer.price,
                            'click': list(offer.click) if offer.click else None}
                           for offer in found]}
    if not found:
        reason = 'shop_offers_not_read'
    elif cash is None:
        reason = 'shop_currency_not_read'
    else:
        affordable = [offer for offer in wanted_offers_now
                      if offer.price is not None and offer.price <= cash-reserve_coins]
        policy_trace=None
        if policy=='learned':
            from .shop_learning import rank_offers
            affordable,policy_trace=rank_offers(affordable,learning or [],dict(value_context or {},
                coins=cash,reserve_coins=reserve_coins,refreshes_used=refreshes_used,
                refresh_limit=refresh_limit,wanted=list(wanted)))
        if affordable:
            offer = affordable[0]
            buy = {'box': list(offer.click), 'name': offer.name, 'price': offer.price,
                   'index': offer.index, 'why': 'gift_plan'}
            reason = 'the_gift_plan_asked_for_this_offer_and_the_shop_covers_it'
        elif wanted_offers_now:
            reason = 'every_offer_the_plan_asked_for_costs_more_than_the_shop_holds'
        elif not wanted_offers(found, wanted):
            reason = 'no_offer_matches_the_gift_plan'
        else:
            reason = 'every_offer_the_gift_plan_asked_for_was_already_bought'
        buttons = shop_refreshes(records, size)
        plain = buttons.get('regular')
        worth_it = (not affordable
                    and bool(list(wanted))
                    and refreshes_used < refresh_limit
                    and plain is not None and plain.box is not None
                    and plain.cost is not None and cash is not None
                    and cash >= 2 * plain.cost and cash-plain.cost>=reserve_coins)
        if worth_it and policy=='learned':
            from .shop_learning import refresh_decision
            worth_it,policy_trace=refresh_decision(learning or [],policy_trace)
        if worth_it:
            refresh = {'box': list(plain.box), 'cost': plain.cost,
                       'reason': 'no_offer_matches_the_gift_plan_yet'}
        # Last, and only when the visit has nothing better: the coins it would carry out
        # of the shop above its cap are spent on the cheapest offer the shelf itself
        # prints.  Every guard is the shelf's own reading -- a printed price inside the
        # budget, a printed box to click -- never a coordinate or a guess, and the same
        # printed price the purchase then has to prove itself against.  The shelf also
        # sells services that are not gifts: window-20261012-210547/frame-0005.json sold
        # "Replace Don Qubote's Sil" at 77, and buying it opened the skill-replacement
        # chooser (frame-0006.json, an UNKNOWN_DIALOG with its own Confirm) instead of
        # the shop's purchase question.  The gift catalog names no such offer (its
        # closest ratio is .48), so when the catalog's own names are supplied the cap
        # only spends on an offer the catalog names, and a shelf of services is left.
        if (buy is None and refresh is None and carry_cap_coins is not None
                and cash > carry_cap_coins):
            forbidden = {name.strip().casefold() for name in blocked if isinstance(name, str)}
            forbidden.update(name.strip().casefold() for name in bought
                             if isinstance(name, str))
            named = {name.strip().casefold() for name in gift_names if isinstance(name, str)}
            cheap = [offer for offer in found
                     if offer.click and offer.price is not None
                     and offer.price <= cash-reserve_coins
                     and offer.name.strip().casefold() not in forbidden
                     and (not named or offer.name.strip().casefold() in named)]
            if cheap:
                offer = min(cheap, key=lambda item: (item.price, item.index))
                buy = {'box': list(offer.click), 'name': offer.name, 'price': offer.price,
                       'index': offer.index, 'why': 'carry_cap'}
                reason = ('the_visit_would_carry_out_more_coins_than_its_cap_holds_so_'
                          'the_shelf_is_spent_on')
            else:
                # The cap could not be honoured and the trace has to say so.  The live
                # window-20261012-221631 spent three cards down to 2400 and then printed
                # ``no_offer_matches_the_gift_plan`` for a shelf whose only unbought offer
                # was the service "Replace Don Qubote's Sil" at 77 -- true of the plan,
                # silent about the 900 coins the cap still wanted to spend.
                reason = ('the_visit_would_carry_out_more_coins_than_its_cap_holds_but_no_'
                          'affordable_unbought_offer_the_shelf_prints_is_the_catalogs')
    return {'currency': cash, 'buy': buy, 'refresh': refresh,
            'policy_trace':locals().get('policy_trace'),
            'confirm': purchase_confirm_target(records, size), 'reason': reason,
            'wanted': list(wanted),
            'offers': [{'index': offer.index, 'name': offer.name, 'price': offer.price,
                        'click': list(offer.click) if offer.click else None}
                       for offer in found]}


def reward_state(record):
    """The encounter reward page's pick counter, as ``{'chosen': n, 'required': m}``."""
    return counter_state(record)


def unselected_reward_successor(record):
    """Independent encounter-reward anchors, not a page label alone.

    Every anchor is a substring test, because the pick counter rides one of the
    lines the OCR keeps whole: the reward page prints ``Selectable 0/1``, so an
    exact-match ``'Selectable' in texts`` never fires, and a floor gift receipt
    clearing its notice onto that page has no provable successor.
    """
    texts = [r['text'].strip() for r in record.get('ocr', []) if r['score'] >= .9]
    count = reward_state(record)
    if (count == {'chosen': 0, 'required': 1}
            and any('Select Encounter Reward Card' in t for t in texts)
            and any('Selectable' in t for t in texts)
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
            dispatch(controller, controller.post_start_app(flows.LAUNCH_INTENT), timeout=30,
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
            # The framework rejects a click whose controller_id is empty while
            # screenshots keep working, so record what the handle says about itself
            # right before the click. One line per click; nothing here changes input.
            self._note_controller_state(controller)
            # A click that never returns must not stay pending: the next capture
            # would talk to a request that is still in flight (the 0xC0000409 crash).
            dispatch(controller, controller.post_click(*point), timeout=10, deadline=deadline,
                     probe=lambda: screencap(controller, timeout=5) is not None,
                     on_soft=lambda why: self.note('window_intent_soft', reason=why))
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


def map_refusal_streak(state, emit):
    """Count consecutive refused map clicks and name the un-resumed case once.

    A refused click has two very different causes and the frame cannot tell them apart:
    the candidate was wrong, or the exploration was never resumed.  One device settled
    it -- before `entry -> Enter -> Dungeon Progress -> Resume` nine clicks moved
    nothing (300..2000 px of animation), and the first click after the resume opened the
    node panel (107860 px).  Naming the second case at three refusals keeps a run from
    looking like a reader defect; `accepted` resets the streak.
    """
    streak = int(state.get('map_refused_streak') or 0) + 1
    state['map_refused_streak'] = streak
    if streak == 3:
        emit('map_clicks_refused_while_the_exploration_may_be_unresumed', streak=streak,
             detail='a resumed exploration answers the first click; a run that is still '
                    'in progress but not resumed refuses all of them')
    return streak


def battle_progress(state, signature, *, rounds):
    """Whether this battle round shows progress, and if not, what that justifies.

    A guard that cannot see progress must not claim its absence.  Live run
    ``packaged-mirror-20261022-014748`` stopped a healthy fight with
    ``battle_progress_stalled`` because the OCR on that theme's HUD returns the ``WAVE``
    and ``TURN`` captions and no values (frames 0050-0058), so ``(None, None)`` was the
    signature on every round and looked perfectly static.  An unread signature is
    therefore not a stall: it is counted separately, and only a long blind stretch is
    handed to the recovery ladder -- which can change the screen -- instead of ending
    the run.

    Returns ``'progress'``, ``'stalled'`` or ``'blind_long'``.
    """
    if signature == (None, None):
        state['battle_blind'] = state.get('battle_blind', 0) + 1
        state['battle_sig'], state['battle_rounds'] = signature, 1
        if state['battle_blind'] > max(rounds * 4, 12):
            return 'blind_long'
        return 'progress'
    state['battle_blind'] = 0
    # ``WAVE 0/x`` is the gap between waves: the turn number cannot advance until the
    # next wave spawns, so an unchanging HUD there is the fight running, not stopping.
    # Live ``build/wr2.png`` shows that gap with the attack animation already playing.
    wave = signature[0] or ''
    if wave.replace(' ', '').startswith('0/'):
        state['battle_sig'], state['battle_rounds'] = signature, 1
        return 'progress'
    if signature == state.get('battle_sig'):
        state['battle_rounds'] = state.get('battle_rounds', 0) + 1
    else:
        state['battle_sig'], state['battle_rounds'] = signature, 1
    return 'stalled' if state['battle_rounds'] > rounds else 'progress'


class MirrorRunner:
    """One bounded window: walk the live dungeon loop and record every page it meets.

    The runner owns the *decisions*; it owns neither the screen nor the input. A
    page arrives from ``observer`` (a live Maa recognition or a replayed archived
    frame) and every input leaves through ``device`` (a Maa controller or an
    in-memory stand-in), which is what lets the same loop run live, run inside an
    agent custom action, and run in a test with no device at all.
    """

    # The framework's own OCR entry, handed in by the agent after construction: the
    # deployment counter needs it to read the enlarged panel (D25).
    run_recognition_direct = None

    def __init__(self, device, *, settings, locale='en', registry=None, store=None,
                 directory=None, journal=None, flow=None, log=None, observer=None,
                 roots=None, run_id=None, result=None):
        self.device = device
        self.settings = settings if isinstance(settings, Settings) else Settings(settings)
        self.locale = locale
        self._locale = None
        self.registry = registry if registry is not None else _load_registry()
        self.store = store
        self.run_id = run_id
        # The verified-run total this window starts from: a saved number of runs is this
        # launch's own instruction, so only the delta since here may satisfy it -- the
        # ledger's all-time count is not a progress bar for the current launch.
        self.run_baseline = None if store is None else _completed_runs(store)
        self.directory = Path(directory) if directory is not None else Path(os.getcwd())
        self.directory.mkdir(parents=True, exist_ok=True)
        self.journal = journal
        if self.store is not None and (self.store.path.parent/'user-mirror-starlight.json').is_file():
            from .mirror_starlight import resolve
            star=resolve(self.store.path.parent,self.store.team_slot)
            if star is not None:
                self.settings=Settings({**self.settings.as_dict(),**{k:star[k] for k in ('graces','grace_budget','grace_auto')}})
                if journal is not None:journal.record('mirror_star_rule_resolved',**star,enhance=False,conversion=False)
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
        if self.grace_transaction is not None:
            # A launch reads the balance it can see.  The number a dead session recorded is
            # history, not a promise; without this every STAR frame of a revived run is
            # refused as "balance changed outside verified purchases".  A pending purchase
            # keeps its number, and the reset is recorded rather than silent.
            self.grace_transaction.reset_baseline('the_session_resumed')
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
        from .shop_transaction import ShopTransaction
        self.shop_transaction=(ShopTransaction(self.store.path.parent/f'user-shop-{self.run_id}.json')
                               if self.store is not None and self.run_id else None)
        from .unknown_exploration import Exploration
        self.exploration=(Exploration(self.store.path.parent/f'user-exploration-{self.run_id}.json',
            self.store.path.parent.parent/'build/learning-review/transitions',self.run_id)
            if self.store is not None and self.run_id else None)

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
            if self.run_baseline is None:
                self.run_baseline = _completed_runs(store)

    def _verified_runs(self):
        """How many complete runs this window has seen settle since it started."""
        if self.store is None or self.run_baseline is None:
            return None
        return _completed_runs(self.store) - self.run_baseline

    def _run_count_reached(self):
        """The player's own number of complete runs, once this window delivered it.

        ``completed_runs`` advances only on ``entry_returned``, which the ledger refuses
        before five verified floors, a final victory and a claimed reward
        (``storage.py259-289``), so an abandoned, expired or given-up run never counts.
        The number is this launch's instruction, not a module budget: a following run
        still pays from its own scope, and a run that cannot start keeps its cleared,
        unclaimed state instead of borrowing an older authorisation.
        """
        target = int(self.settings.run_count or 0)
        seen = self._verified_runs()
        if target <= 0 or seen is None or seen < target:
            return None
        return dict(target=target, completed=seen)

    def _map_verdict(self, **fields):
        """Record a map click verdict together with the party it was judged against.

        `map_player` is only filled after a verdict and `latest_frame()` always returns
        the newest frame, so an offline check compared a party from one frame with
        candidates from another and "proved" the adjacency filter broken (it was not).
        The party the candidate list was filtered against travels with the verdict.
        """
        fields.setdefault('party', self.state.get('map_party'))
        # One place for "this click did not move us".  Four sites record a rejection in
        # the 2026-10-23 tree; wiring the recovery ladder into each of them separately
        # is how one mechanism ends up implemented four times.  Set the flag here,
        # spend it once at the step tail.
        if fields.get('outcome') == 'rejected':
            self.state['map_refused_since_progress'] = True
        self.note('map_click_result', **fields)

    def _note_controller_state(self, controller):
        """Write what the controller handle looks like just before a click.

        A live run posted clicks with ``controller_id=""`` while screenshots kept
        working; knowing whether the handle already looked unbound *before* the
        click (rather than in the request) is what separates a binding-lifetime
        defect from a request-construction one.
        """
        try:
            info = dict(getattr(controller, 'info', None) or {})
        except (RuntimeError, OSError, AttributeError, TypeError):
            info = {}
        empty = [key for key in info if str(key).lower().endswith('id')
                 and not info.get(key)]
        self.note('controller_probe', keys=sorted(str(key) for key in info),
                  empty_id_fields=empty,
                  reason='what the handle said before the click')

    def note(self, name, **fields):
        """Journal one event, when a journal is attached."""
        self.last_event = name
        # Inert bookkeeping: how many events this run has written, so a click can
        # ask whether anything happened after it without scanning the journal.
        self._note_count = getattr(self, '_note_count', 0) + 1
        # Progress has its own clock. A loop can keep taking frames while writing
        # nothing -- live run packaged-mirror-20261022-033911 sat from 07:41:23 with
        # a healthy frame heartbeat and no further event -- and the frame watchdog
        # cannot see that, because frames kept arriving.
        self.artifacts['event_heartbeat'] = time.monotonic()
        if fields.get('page'):
            self._last_page = fields['page']
        if self.journal is not None:
            self.journal.record(name, **fields)
        from .decision_log import lines as decision_lines,signature as decision_signature
        rendered=decision_lines(name,fields)
        if rendered:
            key=decision_signature(name,fields)
            seen=getattr(self,'_logged_decisions',set())
            if key not in seen:
                seen.add(key);self._logged_decisions=seen
                self.artifacts.setdefault('decisions',[]).append(dict(event=name,lines=rendered))
                for line in rendered:
                    try:print('MaaLimbus '+line,flush=True)
                    except (OSError,UnicodeError):pass
        labels={'MAP':'地图','NODE_PANEL':'节点进入','PRE_BATTLE_TEAM':'核对保存编队',
                'BATTLE_HUD':'战斗','BATTLE_PLANNING':'战斗配卡','SHOP':'商店',
                'SHOP_PURCHASE':'商店购买确认','GIFT_PICK':'选择藏品','GIFT_GET':'藏品到账',
                'THEME_PACKS':'选择下一层','RUN_CLAIM':'通关结果'}
        message=None
        if name=='window_intent' and fields.get('page')!=getattr(self,'_ui_phase',None):
            self._ui_phase=fields.get('page')
            message='当前阶段：'+labels.get(self._ui_phase,str(self._ui_phase))
        elif name=='window_map_retry':
            message='地图候选未打开节点，尝试另一候选；次数='+str(fields.get('attempt'))
        elif name=='unknown_exploration_intent':
            message='有界探索：'+str((fields.get('candidate') or {}).get('kind'))
        elif name=='shop_receipt_verified':
            message='商店交易已核对金币与完整货架后继：'+str(fields.get('kind'))
        elif name=='theme_successor_read_retry' and fields.get('attempt') in (1,3,6):
            message='等待主题切换的地图后继；只重新观察，不重拖主题，次数='+str(fields.get('attempt'))
        elif name=='shop_purchase_learning_samples':
            message='购买学习样本已记录：'+str(fields.get('samples'))+'；价值神经模型尚未应用'
        elif name=='pre_battle_identity_report':
            states=fields.get('slot_states') or {}
            message=('编队身份独立核对：测得'+str(states.get('measured'))+'/12，解析出'
                     +str(len(fields.get('resolved') or []))+'位，未解析'
                     +str(len(fields.get('unresolved') or []))+'格。')
        if message:
            try:print('MaaLimbus '+message+'。',flush=True)
            except (OSError,UnicodeError):pass

    def locale_dictionary(self):
        """The label patterns of this run's language, loaded once.

        The planner's fresh bindings (a modal's own close control, the layer under an
        overlay) need the same locale patterns the recognizer classifies with, so the
        file is read here instead of hardcoding English labels into the loop.
        """
        if self._locale is None:
            path = ROOT / f'assets/resource/{self.locale}/locale.json'
            self._locale = json.loads(path.read_text(encoding='utf-8'))
        return self._locale

    def input_helper_line(self):
        """This installation's input-helper posture, for a swallowed-click note."""
        from . import input_helpers
        return input_helpers.line(input_helpers.report(ROOT))

    def _observe(self, deadline=None):
        """One page, from the injected observer, with the journal details attached.

        The frame that comes back is the stall watch's heartbeat: a loop that cannot
        produce a frame is exactly the loop the watch exists for.
        """
        self.artifacts['heartbeat'] = time.monotonic()
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
        if self.exploration is not None and self.exploration.data.get('pending') is not None:
            outcome=self.exploration.finish(frame_file(directory),page)
            self.note('unknown_exploration_reconciled',**outcome,input_sent=False)
        if self.exploration is not None:self.exploration.resolve_episode(frame_file(directory),page)
        # The map floor numeral blinks. A missing digit is not a failed drag:
        # reread the current page within the existing bounded settle budget.
        if page=='MAP' and self.theme_transaction is not None and self.theme_transaction.data and self.theme_transaction.data.get('pending'):
            from .theme_vision import ThemeCatalog
            theme_catalog=ThemeCatalog(ROOT/'assets/resource/base')
            for attempt in range(max(1,settings.unknown_rounds)-1):
                texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
                header=map_header(texts,record.get('size') or (1920,1080))
                if self.theme_transaction.matches(self.run_id,header,theme_catalog):break
                self.note('theme_successor_read_retry',attempt=attempt+1,input_sent=False,
                          expected=self.theme_transaction.data['pending'])
                time.sleep(settings.interval)
                record=self._observe()
                page=resolve_scene(self.registry,directory,record)
                if page!='MAP':break
        frame, candidates = candidates_of(directory, record)
        self.state['map_party'] = record.get('map_party')
        # When a MAP page yields no candidate the reason is one of two very different
        # things -- the image handed to the reading is not the one the evidence file
        # holds, or the party was not read in it.  Record both so the next live stop
        # answers it instead of being guessed at: the offline reading of the same PNG
        # gives the party every time (evidence/runtime/packaged-mirror-20261022-092529/
        # frame-0002.png -> (1628,558)) while the packaged loop reported no candidate.
        if page=='MAP' and not candidates and hasattr(frame,'shape'):
            here=party_point(frame)
            self.note('map_candidates_empty',size=[int(frame.shape[1]),int(frame.shape[0])],
                      party=list(here) if here else None,
                      ocr=len(record.get('ocr') or []))
        # The participant screen (maalimbus/party_vision.py): a node opens it and
        # nothing leaves it until the party is full.  Read here, before the page
        # switch, so a frame the classifier has no name for is still answered --
        # the live loops used to walk into it, leave `Total Participants 0 / 12`
        # untouched, and then sit in front of a battle HUD that never advanced.
        if not settings.observe_only and settings.stop_page != page:
            from . import party_vision
            size = record.get('size') or (1920, 1080)
            party_reads = [Text(t['text'], tuple(t['box']), t['score'])
                           for t in record.get('ocr', [])]
            # The deployment transaction owns this page once it has seen it: it knows
            # the saved order and whether that order is already printed, which is more
            # than "fill the party" can say.  Only an unowned page falls through here.
            # These scenes already have an owner (the deployment reader, which knows
            # the saved order and whether that order is printed).  The party plan only
            # answers a page the classifier cannot name.
            deployment_knows = page in ('PRE_BATTLE', 'PRE_BATTLE_TEAM', 'DEPLOYMENT',
                                        'TEAM_LIBRARY')
            party_plan = None if deployment_knows else party_vision.plan(
                party_reads, size, state.get('party_cards_clicked', 0))
            if party_plan is None and party_vision.is_page(party_reads, size) is False:
                # Say why this frame was not answered instead of returning None
                # silently: an unread counter and a page that is not this one look
                # identical from the outside (D25's lesson, applied to the plan).
                counted = party_vision.participants(party_reads, size)
                if counted is not None or party_vision.looks_like_page(party_reads, size):
                    self.note('party_plan_refused', participants=list(counted) if counted else None,
                              reason='the_counter_and_the_label_did_not_both_read',
                              input_sent=False)
            if party_plan is not None:
                self.note('party_intent', target=list(party_plan['target']),
                          reason=party_plan['reason'],
                          selected=party_plan['selected'], total=party_plan['total'])
                point = party_plan['target']
                self.device.click(point[0], point[1])
                self.artifacts['clicks_sent'] += 1
                if party_plan['action'] == 'select':
                    state['party_cards_clicked'] = int(state.get('party_cards_clicked', 0)) + 1
                time.sleep(settings.interval)
                return self._result(page, list(point), True, None)
        if (not settings.observe_only and settings.stop_page!=page and page=='MAP' and self.exploration is not None
                and (not candidates or state['map_attempts']>=2)):
            recovered=self._explore_unknown(record,frame,candidates)
            if recovered is not None:
                state['map_attempts']=0;state['map_progress'].leave()
                return recovered
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
                    or policy.get('reward_budget_scope')!=self.run_id
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
            from .event_vision import (cyborg_city_choice, garden_refusal_choice,
                                       refusal_choice)
            try:
                city_choice=cyborg_city_choice(record.get('ocr'),record.get('size'),options)
                garden_choice=garden_refusal_choice(record.get('ocr'),record.get('size'),options)
            except ValueError as error:
                # An event the loop has not been taught by name is not a stop: the page
                # still prints the controls it offers, and a page with exactly one
                # decline row can be declined without knowing which event it is.
                self.note('event_identity_not_known',reason=str(error),
                          answer='the page\'s own declining control, if it prints one')
                city_choice = garden_choice = None
            if city_choice is not None:
                choice_index=city_choice
                self.note('cyborg_city_choice',answer='No',source='current exact city question and Yes/No labels',
                          strategy='three No answers disable the factory; each page is freshly identified')
            if garden_choice is not None:
                choice_index=garden_choice
                self.note('garden_refusal_choice',answer='Refuse',
                          source='current exact garden dialogue and two high-confidence controls',
                          strategy='bounded refusal; no inferred gift/healing benefit')
            if city_choice is None and garden_choice is None:
                decline=refusal_choice(record.get('ocr'),record.get('size'),options)
                if decline is not None:
                    choice_index=decline
                    self.note('refusal_choice',answer=options[decline][1],
                              source='the page prints exactly one declining control of two',
                              strategy='bounded refusal; nothing is inferred from the event')
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
            offered = candidates
            candidates = state['map_progress'].remaining(offered)
            if offered and not candidates:
                # Every spot this frame offers has already had its turn, but the page
                # still shows those spots: the bookkeeping is stale, not the reading.
                # evidence/runtime/packaged-mirror-20261022-070445 stopped on
                # `no_candidate_node_observed` while its own last four frames read four
                # candidates each, because all four were already in `tried`.
                state['map_progress'].tried.clear()
                candidates = list(offered)
                self.note('map_tried_reset', offered=len(offered),
                          reason='every_offered_node_was_already_tried')
        heal_options=None
        if page=='HEAL_SINNERS' or page in ('UNKNOWN','UNKNOWN_DIALOG'):
            # The shop's Heal Sinners modal is drawn over the shop page: its three
            # numbered options are read from this frame (live
            # window-20261012-212047/frame-0012.json, whose third option reads
            # '3. Revive a single Sinner.' with its own 100 badge at [1768,611,50,42]).
            # The classifier names the modal off its own title and structure, and this read
            # binds the option the plan may aim at; an UNKNOWN frame that shows the same
            # structure is named here as well, so a window started while the modal is open
            # still reaches the one input that brings a key saved slot back.
            from .shop_revive import heal_sinners_options
            heal_options=heal_sinners_options(
                [Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])],
                record.get('size') or (1920,1080))
            if heal_options is not None:
                page='HEAL_SINNERS'
        sha = record.get('image_sha256')
        if not settings.observe_only and page in WAIT_PAGES:
            if page=='UNKNOWN':
                recovered=self._explore_unknown(record,frame,candidates)
                if recovered is not None:return recovered
                # An animation is not a page.  A battle's skill cutscene carries a
                # handful of fragmentary reads and no control of any kind
                # (evidence/runtime/packaged-mirror-20261022-043142/frame-0069 reads
                # eight fragments: `scading`, `Gaze of Awe`, `179`, `+5`, `5`, `151`).
                # Spending the unknown budget on those is what turned an ordinary
                # end-of-battle animation into `page_unreadable_after_waiting`.
                # A page holds still; an animation does not.  The same unnameable frame
                # twice is a page the reader cannot name, and it keeps its budget.  A
                # frame that changes every time, carrying no control, is a transition.
                moved = sha != state.get('unknown_sha')
                state['unknown_sha'] = sha
                if looks_like_transition(record) and moved:
                    state['transition_seen'] = int(state.get('transition_seen', 0)) + 1
                    if state['transition_seen'] <= max(4, settings.unknown_rounds * 4):
                        self.note('window_transition_wait', page=page,
                                  round=state['transition_seen'], interval_s=settings.interval,
                                  input_sent=False)
                        time.sleep(settings.interval)
                        return self._result(page, None, False, None, waiting=True)
                else:
                    state['transition_seen'] = 0
            state['unknown_seen'] += 1
            turn_waiting=time.monotonic()<state.get('turn_wait_until',0)
            if state['unknown_seen'] > settings.unknown_rounds and not turn_waiting:
                # A page this reader cannot name is still one view: give it the same
                # ladder of gestures before calling the run unreadable.  A battle that
                # is mid-animation and a screen we simply do not know yet look alike
                # from here, and both answer a tap or a drag.
                waiter = dict(reason='page_unreadable_after_waiting')
                recovered = self._recover(page, state, waiter, {})
                if recovered is not None:
                    state['unknown_seen'] = 0
                    return recovered
                stopped = self._record(page, record, frame, candidates, None,
                                       'page_unreadable_after_waiting')
                return self._result(page, None, False, stopped)
            # Loading screens, turn animations and the battle result clear themselves;
            # they are not a refusal, so wait them out instead of stopping the window.
            self.note('window_unknown_wait', page=page, round=state['unknown_seen'],
                      interval_s=settings.interval,submitted_turn_wait=turn_waiting)
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
            verdict = battle_progress(state, signature, rounds=settings.battle_rounds)
            if verdict == 'stalled':
                stopped = self._record(page, record, frame, candidates, None,
                                       'battle_progress_stalled')
                return self._result(page, None, False, stopped, done=True)
            if verdict == 'blind_long':
                waiter = dict(reason='battle_readouts_unreadable_for_a_whole_fight')
                recovered = self._recover(page, state, waiter, candidates)
                if recovered is not None:
                    state['battle_blind'] = 0
                    return recovered
                stopped = self._record(page, record, frame, candidates, None,
                                       'battle_readouts_unreadable_for_a_whole_fight')
                return self._result(page, None, False, stopped, done=True)
            if False:
                # The readouts are not readable on this theme's battle HUD: the OCR
                # returns the two labels and no values (live run
                # packaged-mirror-20261022-014748, frames 0050-0058).  A guard that
                # cannot see progress must not claim its absence, so this round is not
                # counted as a stall; instead a long blind run hands the page to the
                # recovery ladder, which can actually change the screen.
                state['battle_blind'] = state.get('battle_blind', 0) + 1
                if state['battle_blind'] > max(settings.battle_rounds * 4, 12):
                    waiter = dict(reason='battle_readouts_unreadable_for_a_whole_fight')
                    recovered = self._recover(page, state, waiter, candidates)
                    if recovered is not None:
                        state['battle_blind'] = 0
                        return recovered
                    stopped = self._record(page, record, frame, candidates, None,
                                           'battle_readouts_unreadable_for_a_whole_fight')
                    return self._result(page, None, False, stopped, done=True)
                state['battle_sig'], state['battle_rounds'] = signature, 1
            else:
                state['battle_blind'] = 0
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
            if self.deployment_transaction is None:
                stopped=self._record(page,record,frame,candidates,None,'deployment_transaction_or_counter_missing')
                return self._result(page,None,False,stopped,done=True)
            if not team.get('participants'):
                # The counter rolls up while it changes, so a frame that carries none is
                # a frame rather than a page (see _unread_deployment_retry): spend a
                # bounded round re-reading before the run gives up on the deployment.
                retry=self._unread_deployment_retry(state,page,'deployment_counter_not_read')
                if retry is not None:
                    return retry
                stopped=self._record(page,record,frame,candidates,None,'deployment_transaction_or_counter_missing')
                return self._result(page,None,False,stopped,done=True)
            try:
                availability=team.get('availability')
                if availability:
                    import hashlib
                    if hashlib.sha256(frame_file(directory).with_suffix('.png').read_bytes()).hexdigest()!=record.get('image_sha256'):
                        raise ValueError('Deployment availability frame bytes differ')
                    availability=dict(availability,frame=str(frame_file(directory)),image_sha256=record.get('image_sha256'))
                if team['participants'][1]!=len(team['order']) and not team.get('unavailable'):
                    retry=self._unread_deployment_retry(state,page,'deployment_availability_not_read')
                    if retry is not None:return retry
                pending=self.deployment_transaction.data.get('pending') if self.deployment_transaction.data else None
                if pending and self.deployment_transaction.data['scope']==self.run_id:
                    if pending['kind']=='clear' and team['participants'][0]==0:
                        self.deployment_transaction.observe(tuple(team['participants']))
                    elif (pending['kind']=='card' and team['participants'][0]==pending['before']+1
                          and team['states'][pending['card']-1] in ('selected','backup')):
                        self.deployment_transaction.observe(tuple(team['participants']))
                    elif pending['kind']=='card' and pending['card'] in team.get('unavailable',[]):
                        self.deployment_transaction.reconcile_unavailable(self.run_id,tuple(team['participants']),
                                                                         team['unavailable'],availability)
                        self.note('deployment_unavailable_attempt_reconciled',card=pending['card'],proof=availability)
                team.update(self.deployment_transaction.prepare(self.run_id,team['order'],
                    tuple(team['participants']),team.get('numbers'),team.get('unavailable',[]),availability))
                if team.get('order_uncertain'):
                    retry=self._unread_deployment_retry(state,page,'deployment_order_digits_incomplete')
                    if retry is not None:return retry
                    stopped=self._record(page,record,frame,candidates,None,'deployment_order_digits_incomplete_after_retries')
                    return self._result(page,None,False,stopped,done=True)
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
        shop = None
        shop_tx=self.shop_transaction
        notice_ack=None
        if shop_tx is not None and shop_tx.data and shop_tx.data.get('pending') and page not in ('SHOP','SHOP_PURCHASE'):
            pending=shop_tx.data['pending']
            # A purchase's own ``E.G.O Gift GET!`` notice is the one successor a pending
            # purchase may be answered through, and it is answered exactly once: the
            # acknowledgement is written down before the click goes out, so a run that
            # restarts on the notice it already acknowledged stops instead of clicking the
            # same notice twice.  Anything else -- another pending kind, a purchase whose
            # notice was already acknowledged, an unread notice, observe-only -- keeps the
            # pending bytes untouched and stops the run where it stands.
            answerable=(page=='GIFT_GET' and not settings.observe_only
                        and pending.get('kind')=='purchase'
                        and pending.get('stage')=='confirm_intent'
                        and not pending.get('overlay_acknowledgement'))
            # A purchase intent's own click can land on a service modal instead of the
            # shop's question: the live window-20261012-210547 spent its surplus on the
            # shelf offer "Replace Don Qubote's Sil" and got the skill-replacement
            # chooser.  The shelf whose receipt has to be read is behind that modal, so
            # the modal is dismissed through its own close control (the next step's
            # UNKNOWN_DIALOG plan) and the page after it is where the intent is either
            # booked or dropped unspent.  Nothing else is allowed through: any other
            # successor still keeps the pending bytes untouched and stops the run.
            recoverable=(page=='UNKNOWN_DIALOG' and not settings.observe_only
                         and pending.get('kind')=='purchase'
                         and pending.get('stage')=='card_intent')
            if answerable:
                try:
                    notice_ack=shop_tx.reserve_overlay_acknowledgement(
                        self.run_id,pending['visit'],frame_file(directory))
                except (ValueError,OSError) as error:
                    stopped=self._record(page,record,frame,candidates,None,str(error))
                    return self._result(page,None,False,stopped,done=True)
                self.note('shop_notice_acknowledged',page=page,
                          reason='the_purchase_own_gift_get_notice_is_acknowledged_once',
                          target=list(notice_ack),input_sent=False,
                          acknowledgement=shop_tx.data['pending']['overlay_acknowledgement'])
            elif recoverable:
                self.note('shop_receipt_recovery_modal',page=page,stage=pending.get('stage'),
                          reason='the_intent_click_opened_a_modal_and_the_shop_is_behind_it',
                          input_sent=False)
            else:
                stopped=self._record(page,record,frame,candidates,None,'shop_receipt_successor_not_proven')
                return self._result(page,None,False,stopped,done=True)
        if page=='MAP' and shop_tx is not None and shop_tx.data:
            visit=shop_tx.data['current_visit']
            if not shop_tx.data['visits'][visit].get('closed'):
                shop_tx.close_visit(self.run_id,visit,frame_file(directory))
        if page in ('SHOP', 'SHOP_PURCHASE'):
            names=wanted_gifts(state['gift_plan'],settings.gift_keyword,fallback=())
            keywords=[]
            gift_vocabulary=()
            profile=None
            if self.store is not None:
                from .storage import ProfileStore
                from .gift_plan import shop_wanted
                from .gift_vision import GiftCatalog
                profile=next((p for p in ProfileStore(self.store.path.parent/'user-team-profiles.json').load()
                              if p.slot==self.store.team_slot),None)
                if profile is None:raise ValueError('Current saved shop team absent')
                catalog=GiftCatalog(ROOT/'assets/resource/base')
                gift_vocabulary=tuple(catalog.entries)
                from .shop_priority import load as load_shop_priorities
                explicit_priorities=load_shop_priorities(ROOT/'assets/resource/base/shop-priorities.json',catalog)
                names=shop_wanted(profile,catalog,explicit_priorities)
                keywords=sorted(profile.keywords)
                self.note('shop_saved_team_plan',team=profile.slot,keywords=keywords,
                          wanted=names,blocked=sorted(profile.block),input_sent=False,
                          manual_priorities=explicit_priorities,manual_weights_are_learned=False)
            try:
                if shop_tx is None:
                    raise ValueError('shop_transaction_scope_missing')
                d=shop_tx.data
                if d and d.get('pending') and page=='SHOP':
                    shop_reconcile=(shop_tx.reconcile_purchase if d['pending']['kind']=='purchase' else shop_tx.reconcile_refresh)
                    kind=d['pending']['kind']
                    try:
                        shop_reconcile(self.run_id,d['current_visit'],frame_file(directory))
                    except (ValueError,OSError) as error:
                        # A refresh's successor frame can be caught while the shelf is still
                        # being redrawn.  The live window of 2026-10-14 (run
                        # pi-20261014-193945, frame-0004) read two of the six slots and the
                        # counter still showed the pre-refresh coins, so that one frame
                        # proved neither the delta nor the changed shelf.  Wait for a
                        # settled frame instead of stopping -- bounded, and only for a
                        # refresh: the pending intent stays unclaimed through the wait, so
                        # nothing is booked by waiting, and an unchanged page still stops.
                        key=f'{kind}:{d["current_visit"]}'
                        waits=state.setdefault('shop_settle_waits',{})
                        if kind!='refresh' or waits.get(key,0)>=3:
                            raise
                        waits[key]=waits.get(key,0)+1
                        self.note('shop_refresh_settling',page=page,kind=kind,
                                  reason='the_refresh_successor_frame_is_mid_change',
                                  error=str(error),attempt=waits[key],input_sent=False)
                        return self._result(page,None,False,None,waiting=True)
                    self.note('shop_receipt_verified',kind=kind,input_sent=False)
                d=shop_tx.data
                if page=='SHOP':
                    visit=(d['current_visit'] if d and not d['visits'][d['current_visit']].get('closed')
                           else str(len(d['visits'])+1 if d else 1))
                    shop_tx.begin_visit(self.run_id,visit,frame_file(directory),
                        learning_context=dict(keywords=keywords,wanted=sorted(names),reserve_coins=settings.shop_reserve_coins))
                else:
                    if not d or not d.get('pending') or d['pending']['kind']!='purchase' or d['pending']['stage']!='card_intent':
                        raise ValueError('shop_purchase_question_has_no_unsent_matching_intent')
                    visit=d['current_visit']
                state['shop_refreshes']=shop_tx.refreshes_used(self.run_id,visit)
                state['shop_bought']=list(shop_tx.data['bought'])
            except (ValueError,OSError) as error:
                stopped=self._record(page,record,frame,candidates,None,str(error))
                return self._result(page,None,False,stopped,done=True)
            learning=[]
            try:
                from .shop_learning import sync_receipts
                learning=sync_receipts(shop_tx,self.store.path.parent.parent/'build/learning-review/shop',names,keywords)
                from .shop_outcomes import sync as sync_purchase_outcomes
                outcome_samples=sync_purchase_outcomes(shop_tx,
                    self.store.path.parent.parent/'build/learning-review/shop-purchases',self.store.path)
                self.note('shop_purchase_learning_samples',samples=len(outcome_samples),
                          input_sent=False,neural_policy_applied=False,
                          reason='verified_purchase_actions_with_delayed_outcomes_not_yet_trained_value')
            except (ValueError,OSError) as error:
                self.note('shop_learning_unavailable',reason=str(error),input_sent=False)
            shop = shop_state(record, names,
                              bought=[entry['name'] for entry in state['shop_bought']],
                              refreshes_used=state['shop_refreshes'],
                              refresh_limit=settings.shop_refreshes,reserve_coins=settings.shop_reserve_coins,
                              policy=settings.shop_policy,learning=learning,
                              blocked=sorted(profile.block) if profile else (),
                              carry_cap_coins=settings.shop_carry_cap_coins,
                              gift_names=gift_vocabulary,
                              value_context=dict(floor=state['floor_now'],keywords=keywords))
            if page=='SHOP' and shop:
                # A revive planned at this shop is booked from the shop's own counter: the
                # Heal Sinner service is paid for with the run's in-run currency, so the
                # step back onto the panel has to show it lower by exactly the price the
                # modal printed.  The receipt is consumed once, and a panel that does not
                # prove it is recorded instead of believed.
                receipt=state.pop('revive_receipt',None)
                if receipt:
                    before=receipt.get('coins_before'); cost=receipt.get('cost')
                    after=shop.get('currency')
                    proof=dict(source='shop_currency_delta',
                               image_sha256=record.get('image_sha256'))
                    if (self.deployment_transaction is not None and isinstance(before,int)
                            and isinstance(after,int) and isinstance(cost,int)
                            and before-after==cost):
                        self.deployment_transaction.book_revive(
                            receipt['card'],cost,before,after,proof=proof)
                        self.note('shop_revive_booked',card=receipt['card'],cost=cost,
                                  coins_before=before,coins_after=after,proof=proof,
                                  reason='the_shop_s_own_counter_moved_by_the_price_the_modal_printed',
                                  input_sent=False)
                    else:
                        self.note('shop_revive_receipt_not_proven',card=receipt.get('card'),
                                  cost=cost,coins_before=before,coins_after=after,proof=proof,
                                  reason='the_shop_s_counter_did_not_show_the_revive_price',
                                  input_sent=False)
                # A key slot the deployment page's own proof could not field comes back
                # before the visit spends anything else: the operator's standing rule is
                # that a Sinner in the first seven slots of the saved order must be
                # revived, and the shop's Heal Sinner service is the only way back.  The
                # card list is the deployment transaction's own proof, never a guess at
                # a portrait, and the click box is the service's own two label tokens.
                from .shop_revive import heal_sinner,key_losses,saved_order,unavailable_sinners
                store_state=self.deployment_transaction.data if self.deployment_transaction is not None else None
                lost=key_losses(unavailable_sinners(store_state),saved_order(store_state))
                service=heal_sinner([Text(t['text'],tuple(t['box']),t['score']) for t in record['ocr']],
                                    record.get('size')) if lost else None
                if service is not None:
                    shop['revive']={'box':list(service.box),'cost':service.cost,
                                    'cost_box':list(service.cost_box) if service.cost_box else None,
                                    'cards':lost}
                    state['revive_receipt']=dict(card=lost[0],cost=service.cost,
                                                 coins_before=shop.get('currency'))
                    self.note('shop_revive_planned',cards=lost,cost=service.cost,
                              coins_before=shop.get('currency'),
                              reason='a_key_saved_slot_is_dead_and_the_shop_sells_the_way_back',
                              input_sent=False)
            self.note('shop_policy',mode=settings.shop_policy,refresh_limit=settings.shop_refreshes,
                      reserve_coins=settings.shop_reserve_coins,
                      carry_cap_coins=settings.shop_carry_cap_coins,
                      decision=shop.get('policy_trace'),input_sent=False)
            if page=='SHOP' and shop:
                chosen=shop.get('buy') or {};offers=shop.get('offers') or []
                from .shop_vision import wanted_offers,Offer
                # Reuse the exact matching/order function that chose the purchase.
                matches=wanted_offers([Offer(o['index'],o['name'],(),o['price'],None,tuple(o['click']) if o.get('click') else None) for o in offers],names,
                    [entry['name'] for entry in state['shop_bought']])
                ranks={o.index:len(matches)-n for n,o in enumerate(matches)}
                rows=[]
                for offer in offers:
                    price=offer['price'];eligible=offer['index'] in ranks
                    affordable=price is not None and shop['currency'] is not None and price<=shop['currency']-settings.shop_reserve_coins
                    rows.append(dict(name=offer['name'],price=price,manual_weight=(explicit_priorities if profile else {}).get(offer['name'],0),
                        score=ranks.get(offer['index']),status='可购买' if eligible and affordable else '不在候选队列' if not eligible else '超过可用金币',
                        chosen=chosen.get('index')==offer['index']))
                self.note('shop_decision_ranking',ranking=rows,currency=shop['currency'],reserve=settings.shop_reserve_coins,
                    refresh_limit=settings.shop_refreshes,reason=shop['reason'],learning=shop.get('policy_trace'),input_sent=False)
            if page=='SHOP_PURCHASE' and shop:
                from .shop_vision import (matching_purchase_question, native_purchase_dialog,
                                          purchase_dialog_answer)
                texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record['ocr']]
                pending=shop_tx.data.get('pending') if shop_tx is not None else None
                if pending and pending.get('name') and pending.get('price'):
                    answer=purchase_dialog_answer(texts,pending['name'],pending['price'],record['size'],
                                                  coins=pending.get('coins'))
                    if answer is None:
                        shop['confirm']=matching_purchase_question(texts,pending['name'],pending['price'],record['size'],coins=pending.get('coins'))
                    elif answer[0]=='purchase':
                        shop['confirm']=answer[1]
                    else:
                        # The modal's own Cancel answers a question this project did not
                        # reserve, so the shelf is re-read on the next frame instead of
                        # the run ending over one unreadable band or a drifted counter.
                        shop['cancel']=answer[1]
                        shop['cancel_reason']='the_dialog_does_not_name_the_reserved_gift_at_its_price'
                else:
                    # A question nobody reserved (the operator's own click, or a run that
                    # died mid-dialog): nothing may authorize a purchase this project did
                    # not plan, so the modal's own Cancel is the only input offered here.
                    dialog=native_purchase_dialog(texts,record['size'])
                    if dialog is not None:
                        shop['cancel']=list(dialog['cancel'].box)
                        shop['cancel_reason']='a_purchase_question_this_run_never_reserved'
            self.note('shop_offers', currency=shop['currency'] if shop else None,
                      reason=shop['reason'] if shop else 'shop_page_not_read',
                      buy=shop['buy'] if shop else None,
                      refresh=shop['refresh'] if shop else None,
                      confirm=shop['confirm'] if shop else None,
                      offers=shop['offers'] if shop else [])
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
                pending=(self.floor_gift_transaction.data or {}).get('pending')
                if pending and pending.get('kind')=='pick':
                    self.floor_gift_transaction.recover_pick(self.run_id,floor_offers,gift,
                        frame_file(directory),self.floor_gift_catalog)
                    self.note('floor_gift_pending_pick_reconciled',input_sent=False,
                              successor=str(frame_file(directory)),count=gift)
                elif pending and pending.get('kind')=='receipt':
                    # The notice that pick produced was never booked before the attempt that
                    # made it ended. A fresh floor gift page proves that receipt's successor
                    # the same way the settling path would, and the retained notice frame is
                    # re-read by hash, so nothing is assumed and no input is replayed
                    # (dist/MaaLimbus/evidence/runtime/pi-20261015-172554 stopped with
                    # floor_gift_previous_transaction_unresolved on exactly this page).
                    self._resolve_floor_receipt(self.floor_gift_transaction,'GIFT_PICK','',
                                                directory,record)
                d=self.floor_gift_transaction.prepare(self.run_id,floor_offers,gift,frame_file(directory))
                profile=next((p for p in ProfileStore(self.store.path.parent/'user-team-profiles.json').load()
                              if p.slot==self.store.team_slot),None)
                if profile is None:raise ValueError('floor_gift_saved_team_missing')
                ranking=floor_gifts.rank(floor_offers,profile,d['selected'])
                for offer in floor_offers:
                    if offer.unpriced:
                        from .unknown_exploration import queue_trial
                        proposal=queue_trial(frame_file(directory),offer,self.run_id,
                            self.store.path.parent.parent/'build/learning-review')
                        self.note('unclassified_trial_review_queued',**proposal,title=offer.title,input_sent=False)
                if not ranking and gift['chosen']<gift['required']:
                    ranking=floor_gifts.exploration_rank(floor_offers,profile,d['selected'])
                    self.note('floor_gift_bounded_exploration_ranking',ranking=ranking,
                        reason='player_authorized_unknown_game_choices',learned_applied=False)
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
                    if not ranking:
                        unpriced=[o.title for o in floor_offers if o.unpriced]
                        raise ValueError('floor_gift_unpriced_choices_insufficient'
                                         if unpriced else 'floor_gift_no_allowed_offer')
                    selected=next(o for o in floor_offers if o.title==ranking[0]['title'])
                    gift.update(target=list(selected.box),title=selected.title)
                self.note('floor_gift_ranking',team=profile.slot,ranking=ranking,
                          unpriced=[dict(title=o.title,printed=o.unpriced)
                                    for o in floor_offers if o.unpriced],
                          selected=d['selected'],selection_source=floor_offers[0].selection_source,
                          proof=str(frame_file(directory)))
            except (ValueError,FileNotFoundError) as error:
                stopped=self._record(page,record,frame,candidates,None,str(error))
                return self._result(page,None,False,stopped,done=True)
        else:
            state['gift_picks'] = 0
        floor_receipt=None
        receipt_booked=False
        floor_tx=self.floor_gift_transaction
        if floor_tx is not None and floor_tx.data and floor_tx.data['scope']==self.run_id and floor_tx.data['commit_sent'] and not floor_tx.data['completed']:
            from . import initial_gifts
            texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
            floor_receipt=initial_gifts.receipt_name(texts,record.get('size') or (1920,1080))
            d=floor_tx.data
            remaining=[n for n in d['selected'] if n not in [r['title'] for r in d['receipts']]]
            def _attributed(data):
                pending=data.get('pending') or {}
                printed=pending.get('granted')
                left=[n for n in data['selected'] if n not in [r['title'] for r in data['receipts']]]
                return (pending.get('kind')=='commit' and bool(floor_receipt)
                        and (any(initial_gifts.same_name(floor_receipt,n) for n in left)
                             or bool(printed and initial_gifts.same_name(floor_receipt,printed))))
            # A notice page whose own name plate answers no pick still proves the press:
            # live run pi-20261014-072228 printed 'Dark Vestige' for a selection the run
            # really made. The receipt stage labels that name; reading it as an
            # unattributable page here is what stopped the run.
            notice=_attributed(d) or (page=='GIFT_GET'
                                      and floor_tx.notice_matches_a_pick(floor_receipt))
            if page!='GIFT_GET' or not notice:
                # An outstanding receipt whose own confirm already landed is resolved from
                # the retained pair: the notice the run booked, its hash-checked frame, and
                # this fresh successor. It books what the page printed instead of stopping.
                # The successor is any page the settling rule itself honours, not only
                # another notice: a cleared notice usually lands on the encounter reward
                # page, and demanding a notice there stranded the receipt on every later
                # step. A notice successor still has to attribute the next commit, because
                # that page is the one the run goes on to click.
                booked=(page in RECEIPT_SUCCESSOR_PAGES
                        and (d.get('pending') or {}).get('kind')=='receipt'
                        and self._resolve_floor_receipt(floor_tx,page,floor_receipt,directory,record)
                        and (_attributed(floor_tx.data) if page=='GIFT_GET'
                             else bool(floor_tx.data['completed'])))
                if not booked:
                    stopped=self._record(page,record,frame,candidates,None,'floor_gift_receipt_unknown_repeated_or_pending')
                    return self._result(page,None,False,stopped,done=True)
                receipt_booked=True
        plan_controls=dict(self.controls)
        # One refused click is enough: the streak counts every click the game did not
        # take, and a map that refuses one node is the map that refuses them all.
        if page=='MAP' and int(state.get('map_refused_streak') or 0)>=1:
            # Nine refusals before `entry -> Enter -> Dungeon Progress -> Resume` and one
            # click after it (see `window.plan_map`): a map that is read but refuses every
            # node is a run that was never resumed, and the resume lives behind the map's
            # own progress control at the top right of the page.
            plan_controls['map.progress_button']=list(MAP_PROGRESS_CONTROL)
            # Carry the intent across the page change: the streak is reset when the
            # progress panel takes over, so the panel below cannot read it.  Live run
            # `packaged-mirror-20261023-053843` opened the panel four times and then
            # fell into `window_recovery`, because by then the streak was 0.
            state['resume_requested']=True
        if page=='TUTORIAL' and record.get('overlay_dismissal',{}):
            closer=record['overlay_dismissal']
            if closer.get('kind')=='tutorial_book':
                plan_controls['tutorial.book_close']=closer['box']
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
            # The saved deployment is only really on the screen when an independent
            # teacher reads all twelve slots that way, and that reading is journaled
            # per distinct frame. It never sends input and never certifies itself:
            # a slot whose card was not measured there, or whose caption did not
            # resolve, is reported as a gap rather than counted as a match.
            sha=record.get('image_sha256')
            if sha and sha!=state.get('identity_sha'):
                saved_order=(team or {}).get('order') or ()
                badges=(team or {}).get('numbers') or ()
                evidence=pre_battle_identity_evidence(directory,record,saved_order,badges)
                if evidence is not None:
                    state['identity_sha']=sha
                    self.note('pre_battle_identity_report',**evidence)
        if page=='DUNGEON_PROGRESS':
            # The panel prints Progress / Forfeit / Continue / To Window / Config. Its
            # planner only ever presses Continue, but nothing bound that anchor, so a
            # resumed-in-progress run stopped here (`packaged-mirror-20261022-084358`:
            # the resume plan opened the panel, then `continue_button_not_anchored`).
            # Bind the row the panel actually draws, and never Forfeit.
            for row in (record.get('ocr') or []):
                text=str(row.get('text') or '').strip().lower()
                if text=='continue':
                    plan_controls['dungeon_progress.continue_button']=[int(v) for v in row['box']]
                elif text=='resume':
                    # The entry's own progress dialog offers Resume / Halt Exploration /
                    # Cancel; that Resume is the control that re-enters a suspended
                    # exploration (a paused panel's Continue only closes the panel and
                    # hands back the same map that refuses every node click).
                    plan_controls['dungeon_progress.resume_button']=[int(v) for v in row['box']]
                elif text.endswith('window'):
                    # "To Window" / "Window": the pause panel's way back to the entry,
                    # where the run can actually be resumed.
                    plan_controls['dungeon_progress.window_button']=[int(v) for v in row['box']]
            # One refused click is evidence enough: live, a run that opened with
            # `a_run_is_still_in_progress` refused twice and then wedged, never
            # reaching three.  The resume chain is reversible, so paying it once
            # early costs less than a run that never gets there.
            if int(state.get('map_refused_streak') or 0)>=1 or state.get('resume_requested'):
                plan_controls['dungeon_progress.resume_via_entry']=True
        if page=='RESUME_DIALOG':
            # The entry asks whether to rejoin the run that is still in progress.
            # The panel's own words are `Resume` [902,579,114,34] (live
            # `evidence/runtime/packaged-mirror-20261023-054332/frame-0027.json`,
            # 41 OCR rows), and the chain reaches this page only after it has
            # already left for the entry on purpose, so the answer is `Resume`.
            for row in (record.get('ocr') or []):
                text=str(row.get('text') or '').strip().lower()
                if text=='resume' or text.endswith(' resume') or text.startswith('resume '):
                    plan_controls['resume.resume_button']=[int(v) for v in row['box']]
                    break
        if page=='UNKNOWN_DIALOG':
            # A modal that named no page is dismissed through its own close control,
            # bound from this frame: the modal is drawn wherever the page under it puts
            # it, and its other control (Confirm) spends a resource the run never chose.
            from .vision import dialog_dismissal
            texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
            box=dialog_dismissal(texts,record.get('size') or (1920,1080),self.locale_dictionary())
            if box:plan_controls['unknown_dialog.close']=list(box)
            # One refused click is evidence enough: live, a run that opened with
            # `a_run_is_still_in_progress` refused twice and then wedged, never
            # reaching three.  The resume chain is reversible, so paying it once
            # early costs less than a run that never gets there.
            if int(state.get('map_refused_streak') or 0)>=1 or state.get('resume_requested'):
                # Leaving for the entry asks a confirmation of its own; the generic
                # dismissal would close it and hand back the same paused panel
                # (live: 09:24:16 `the_unexpected_dialog_is_dismissed_with_its_own_close`
                # returned to DUNGEON_PROGRESS twice in a row).
                for row in (record.get('ocr') or []):
                    if str(row.get('text') or '').strip().lower() in ('confirm','yes','ok'):
                        plan_controls['unknown_dialog.confirm']=[int(v) for v in row['box']]
                        plan_controls['leave_for_entry_pending']=True
                        break
        if page=='HEAL_SINNERS' and heal_options is not None:
            plan_controls['heal_sinners.revive']=list(heal_options.revive_box)
        if page in ('REVIVE_PICK','REVIVE_DONE'):
            # The modal's second step asks for the Sinner itself (live
            # evidence/runtime/window-20261012-213008/frame-0002.json reads 'Select the
            # Sinner to revive.' [102,567,330,36] with the party bar along the bottom of the
            # screen, the dead card 6's portrait highlighted and its number the one this OCR
            # never reads), and its own bottom-right button then answers that pick.  Which
            # card is dead is the deployment page's own proof, so the bar box comes from the
            # deck that proof names; only one input leaves per picker frame, so a picker that
            # answers a click with itself gets the modal's own button answered next, never
            # its portrait clicked twice (a second click takes a selection back, live
            # window-20261012-214600).
            from .shop_revive import (key_losses,modal_bottom_control,picker_slot,saved_order,
                                      unavailable_sinners)
            store_state=(self.deployment_transaction.data
                         if self.deployment_transaction is not None else None)
            texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
            size=record.get('size') or (1920,1080)
            words=self.locale_dictionary()
            if page=='REVIVE_DONE':
                # Somebody is back ("<Sinner>, revived, returns to battle.") and the modal's
                # own button is now Leave, which hands the panel back to the shop.  The row
                # above it would heal again for another 100 and is never aimed at here.
                state.pop('revive_pick_frames',None)
                box=modal_bottom_control(texts,[words.get('leave',r'^Leave$')],size)
                if box is not None:
                    plan_controls['revive_done.leave']=box
                    self.note('revive_done_leave_bound',box=box,
                              reason='the_modal_s_own_bottom_right_button_is_the_way_back',
                              input_sent=False)
            else:
                picked=state.get('revive_pick_frames',0)
                state['revive_pick_frames']=picked+1
                if picked:
                    box=modal_bottom_control(texts,[words.get('select',r'^Select$')],size)
                    if box is not None:
                        plan_controls['revive_pick.action']=box
                        self.note('revive_pick_confirm_bound',box=box,
                                  reason='the_modal_s_own_bottom_right_button_answers_the_pick',
                                  input_sent=False)
                else:
                    box=picker_slot(unavailable_sinners(store_state),saved_order(store_state),
                                    size)
                    if box is not None:
                        plan_controls['revive_pick.slot']=list(box)
                        self.note('revive_pick_slot_bound',box=list(box),
                                  cards=key_losses(unavailable_sinners(store_state),
                                                   saved_order(store_state)),
                                  reason='the_picker_asks_for_the_card_the_deployment_page_could_not_field',
                                  input_sent=False)
        elif state.pop('revive_pick_frames',None) is not None:
            pass
        if page=='GIFT_GET' and notice_ack is not None:
            # The notice's own Confirm was just re-proved against this very frame and
            # stored as the pending purchase's acknowledgement, so that box -- not the
            # static registry anchor -- is the only target this page may click.  It is
            # the one control on the notice that reads a gift back to the shelf; the
            # neighbouring control would spend currency the run never chose.
            plan_controls['gift_get.confirm_button']=list(notice_ack)
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
                # A revived scope reuses its id while the counter on screen belongs to the
                # attempt being shown now; adopt it instead of claiming a mismatch.
                if self.initial_transaction.rebase_visible(self.run_id,count,frame_file(directory)):
                    self.note('initial_gift_rebased',counter=list(count))
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
            previous_scope=self.run_id
            reconcile(self.store,page=page,proof=frame_file(directory))
            self.run_id=self.store.start()
            team['wanted']=self.store.team_slot
            self.result['run_ledger']=dict(path=str(self.store.path),run=self.run_id,
                                          team=self.store.team_slot,rotation=self.store.data['rotation'])
            if previous_scope!=self.run_id:
                # These files are named by scope. Preserve the old run's pending
                # evidence; never book the next run into an old shop/review file.
                from .shop_transaction import ShopTransaction
                from .unknown_exploration import Exploration
                self.shop_transaction=ShopTransaction(self.store.path.parent/f'user-shop-{self.run_id}.json')
                self.exploration=Exploration(self.store.path.parent/f'user-exploration-{self.run_id}.json',
                    self.store.path.parent.parent/'build/learning-review/transitions',self.run_id)
                self.note('mirror_run_scope_changed',previous=previous_scope,current=self.run_id,
                          team=self.store.team_slot,rotation=self.store.data['rotation'],old_evidence_preserved=True)
            state['entry_reconciled']=True
            state['run_settled_itself']=False
            if self.grace_transaction is not None:
                # A launch reads the balance it can see: the previous session's number is
                # history once nothing is pending, and a run that resumed a dead session
                # would otherwise refuse every later frame as "changed outside purchases".
                stale = self.grace_transaction.data
                if not stale or stale.get('scope') != self.run_id:
                    self.grace_transaction.begin(self.run_id,state['grace_wanted'],
                                                 settings.grace_budget,frame_file(directory))
                else:
                    # Same scope, resumed: keep the record of what was bought, drop the
                    # dead session's balance so this frame's number can be adopted.
                    self.grace_transaction.reset_baseline('the_session_resumed')
        if page=='DUNGEON_TEAM' and team and team['selected']!=team['wanted']:
            from .team_navigation import prepare
            rows=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
            location=prepare((self.store.path.parent if self.store else directory)/'user-team-navigation.json',
                             self.run_id,rows,record.get('size') or (1920,1080),team['wanted'])
            team.update(visible_rows=location.get('rows',[]),visible_target=location.get('target'),navigation=location)
            self.note('team_list_search',wanted=team['wanted'],selected=team['selected'],navigation=location)
        graces = None
        transaction=self.grace_transaction
        if page in ('STAR_GRACES','STAR_CONFIRM') and transaction is not None:
            try:
                records=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
                available=available_starlight(records,record.get('size') or (1920,1080))
                if page=='STAR_GRACES' and transaction.data and transaction.data.get('pending'):
                    recovered=transaction.recover(self.run_id,state['grace_wanted'],settings.grace_budget,
                                                  available,frame_file(directory))
                    self.note('grace_purchase_recovered',card=recovered['card'],cost=recovered['cost'],
                              available=available,input_sent=False,proof=str(frame_file(directory)))
                if settings.grace_auto:
                    priorities=[int(n) for n in settings.graces.split(',') if n]
                    costs=None
                    if page=='STAR_GRACES':
                        from .grace_vision import observed_board
                        image,_=latest_frame(directory)
                        board=observed_board(image,records,priorities) if image is not None else None
                        if board is None:raise ValueError('Automatic star candidate costs not proven')
                        costs=board['costs']
                    state['grace_wanted']=transaction.seal_auto(self.run_id,priorities,
                        settings.grace_budget,available,costs,frame_file(directory))
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
                retry = self._unread_grace_retry(state, page,
                                                 'starlight_available_balance_not_proven')
                if retry is not None:
                    return retry
                stopped = self._record(page, record, frame, candidates, None,
                                       'starlight_available_balance_not_proven')
                self._detail(requested=state['grace_wanted'],
                             bought=sorted(state['grace_bought']))
                return self._result(page, None, False, stopped, done=True)
            from .grace_vision import observed_board
            image, _ = latest_frame(directory)
            board=observed_board(image,records,state['grace_wanted']) if image is not None else None
            if board is None:
                retry = self._unread_grace_retry(state, page,
                                                 'configured_grace_costs_not_proven')
                if retry is not None:
                    return retry
                stopped=self._record(page,record,frame,candidates,None,'configured_grace_costs_not_proven')
                self._detail(requested=state['grace_wanted'],
                             bought=sorted(state['grace_bought']))
                return self._result(page,None,False,stopped,done=True)
            state['grace_read_attempts'] = 0
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
                # The page's balance is the hard limit on how much of the configured set
                # one run can buy: live 2026-10-12 the Graces page offered 60 starlight
                # against a 100-starlight selection, so 2,4,5 were bought and the run
                # then refused the page forever (config/user-grace-transaction.json,
                # selected [2,4,5], spent 60). The wish list narrows onto the affordable
                # prefix -- the same freeze an automatic plan gets -- so the run can
                # leave the page, and what Enter verifies is that narrowed plan.
                try:
                    narrowed=transaction.seal_affordable(
                        self.run_id,[int(n) for n in str(settings.graces).split(',') if n.strip()],
                        settings.grace_budget,total_budget,board['costs'],frame_file(directory))
                except ValueError as error:
                    stopped=self._record(page,record,frame,candidates,None,
                                         'configured_graces_incomplete_within_budget')
                    self._detail(requested=state['grace_wanted'],
                                 bought=sorted(state['grace_bought']), available=available,
                                 budget=total_budget, unaffordable=sorted(remaining),
                                 costs={index: board['costs'][index - 1]
                                        for index in state['grace_wanted']},
                                 error=str(error))
                    return self._result(page,None,False,stopped,done=True)
                self.note('grace_selection_narrowed_to_the_affordable_prefix',
                          requested=sorted(state['grace_wanted']),affordable=narrowed,
                          bought=sorted(state['grace_bought']),available=available,
                          budget=total_budget,unaffordable=sorted(remaining))
                state['grace_wanted']=narrowed
                wanted=plan_purchases(state['grace_wanted'],total_budget,
                                      bought=state['grace_bought'],costs=board['costs'])
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
        if page == 'MAP' and candidates:
            # Breadth over the nodes this page offers, not depth on the first one.
            tried = state.setdefault('map_tried', [])
            if len(tried) >= len(candidates):
                tried.clear()
            # The neighbour of where the party stands is the best bet, but it is only a
            # preference: `tried` is bookkeeping for the whole page, so dropping the other
            # candidates would leave the two lengths in different coordinate systems and
            # the page would run out of candidates after a couple of refusals
            # (evidence/runtime/packaged-mirror-20261022-065931 stopped after 7 steps
            # that way).  Order, never filter.
            here = state.get('map_player')
            if here:
                def point_of(candidate):
                    if isinstance(candidate, dict):
                        return candidate['point']
                    box = candidate
                    return (box[0] + box[2] / 2, box[1] + box[3] / 2)
                near = [c for c in candidates if one_step_from(point_of(c), here)]
                far = [c for c in candidates if not one_step_from(point_of(c), here)]
                candidates = near + far
            choice_index = next_untried(candidates, tried)
            chosen = candidates[choice_index]
            tried.append([int(v) for v in (chosen['box'] if isinstance(chosen, dict)
                                           else chosen)])
            self.note('map_candidate_breadth',index=choice_index,
                      tried=len(tried),offered=len(candidates),
                      reason='try_the_next_destination_instead_of_the_same_node')
        elif page != 'MAP':
            state.pop('map_tried', None)
        if page=='MAP' and not candidates:
            # The stop the live loops keep reporting is `no_candidate_node_observed`, and the
            # two causes behind it read very differently: either the record carries a
            # different frame size than the evidence PNG the reading agrees with offline, or
            # the observation itself came back empty.  Record both with the same stop, so the
            # next run answers it instead of needing another instrumented pass.
            self.note('map_candidates_empty',scene=record.get('scene'),
                      size=record.get('size'),ocr=len(record.get('ocr') or []),
                      reason='the_map_reader_offered_no_destination')
        plan = plan_step(page, controls=plan_controls, arrows=arrows,
                         difficulty=difficulty,
                         start_box=record.get('start_box'),
                         auto_assign=record.get('auto_assign_buttons'),
                         battle_assignment=settings.battle_assignment,
                         battle_previous=state.get('battle_previous'),
                         candidates=candidates, candidate_index=choice_index,
                         team=team, reward=reward, gift=gift, cards=cards,
                         graces=graces, initial=initial, check=check, defeat=defeat,
                         search={'mode': settings.gift_search},
                         shop=shop,
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
                 'battle_assignment':settings.battle_assignment,
                 'check': check, 'defeat': defeat, 'shop': shop,
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
            # D34: a missing control is a *class* of refusal, not 46 page-specific
            # endings.  An anchor miss is exactly as re-readable as a `no_...`
            # reading miss -- the frame may have settled mid-transition and the
            # button arrived on the next one -- so it spends the same bounded
            # reading retry instead of ending the run.  `page_tries` still bounds
            # it, and nothing is sent while we look again.
            retry_reading = reread_allowed(
                plan, attempts=state['page_attempts'],
                tries=settings.page_tries, observe_only=settings.observe_only)
            self.artifacts['steps'].append(entry)
            if retry_reading:
                state['page_attempts'] += 1
                entry['stopped'] = 'page_reading_retried'
                self.note('window_page_retry', reason=plan.get('reason'),
                          attempt=state['page_attempts'],
                          **({'anchor': plan['anchor']} if plan.get('anchor') else {}))
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
            # Whether the card was a known duplicate explains a substituted receipt.
            picked=next((o for o in (floor_offers or []) if o.title==gift['title']),None)
            self.floor_gift_transaction.intent(gift['title'],
                dict(chosen=gift['chosen'],required=gift['required']),frame_file(directory),
                owned=bool(picked is not None and picked.owned))
        if plan.get('reason')=='refuse_proven_owned_single_free_gift':
            self.floor_gift_transaction.refuse_owned(floor_offers,
                dict(chosen=gift['chosen'],required=gift['required']),frame_file(directory))
        if plan.get('reason')=='confirm_proven_owned_gift_refusal':
            self.floor_gift_transaction.refusal_confirm_intent(self.run_id,frame_file(directory))
        if plan.get('reason')=='select_takes_the_picked_floor_gifts':
            self.floor_gift_transaction.commit(frame_file(directory))
        if floor_receipt and not receipt_booked:
            # Only an outstanding commit expects a receipt, and never a page that has
            # just booked one above: this reader is a loose middle-band text match, so
            # the encounter reward page prints '2~3 E.G.O Gift' straight into it. An
            # intent the transaction cannot prove stops the run before any input.
            pending=(self.floor_gift_transaction.data or {}).get('pending') or {}
            if pending.get('kind')=='commit':
                try:
                    self.floor_gift_transaction.receipt_intent(floor_receipt,frame_file(directory),
                                                               on_notice_page=(page=='GIFT_GET'))
                except ValueError as error:
                    entry.update(passed=False,reason=str(error),
                                 stopped='unverified_floor_gift_receipt_intent')
                    self.artifacts['steps'].append(entry)
                    return self._result(page,None,False,entry['stopped'],done=True)
        if page=='GIFT_GET' and state.get('initial_receipt'):
            from .storage import write_json
            self.initial_transaction.data['receipt_pending']=state['initial_receipt']
            write_json(self.initial_transaction.path,self.initial_transaction.data)
        if plan.get('reason')=='enable_hard_on_proven_floor_one':
            from .storage import write_json
            path=self.store.path.parent/'user-difficulty-transaction.json'
            write_json(path,dict(scope=self.run_id,pending=dict(before='normal',requested='hard',proof=str(frame_file(directory)))))
        if plan.get('reason')=='the_floor_theme_pack_is_pulled_down_to_be_taken':
            # The floor on screen is being chosen now; a selection recorded by a dead
            # attempt for this same floor is history, not a reason to stop the launch.
            if self.theme_transaction.rebase_visible(self.run_id):
                self.note('theme_selection_rebased',floor=theme_choice['floor'])
            self.theme_transaction.intent(self.run_id,theme_choice['floor'],theme_choice['name'],frame_file(directory))
        if page=='PRE_BATTLE_TEAM' and plan.get('reason') in ('clear_inherited_participant_order_before_saved_deployment','team_card_joins_the_next_unpicked_identity'):
            kind='clear' if plan['reason'].startswith('clear_inherited') else 'card'
            self.deployment_transaction.intent(kind,tuple(team['participants']),(plan.get('detail') or {}).get('card_index'))
        point = None
        if page == 'SHOP_PURCHASE' and plan.get('reason') == (
                'the_dialogs_own_cancel_answers_a_question_this_project_did_not_reserve'):
            # The modal is not the question this project reserved, so the reservation
            # is retired with the Cancel that answers it (shop_transaction.
            # retire_pending): a stale intent would otherwise keep the shelf from
            # being bought from at all -- every purchase would be refused as already
            # reserved -- and the run would loop on this one dialog.
            if shop_tx is not None and shop_tx.data.get('pending'):
                shop_tx.retire_pending(self.run_id, shop_tx.data['current_visit'],
                                       (plan.get('detail') or {}).get('why'))
        if page in ('SHOP','SHOP_PURCHASE') and plan.get('reason') in (
                'buying_the_gift_the_gift_plan_asked_for',
                'spending_the_coins_this_visit_would_carry_out_on_the_shelf',
                'refreshing_the_shelf_for_the_gift_the_plan_wants',
                'confirming_the_purchase_the_shop_asked_about'):
            visit=shop_tx.data['current_visit']
            if plan['reason'] in ('buying_the_gift_the_gift_plan_asked_for',
                                  'spending_the_coins_this_visit_would_carry_out_on_the_shelf'):
                target=shop_tx.reserve_purchase(self.run_id,visit,plan['detail'],shop['currency'],frame_file(directory),
                    reserve_coins=settings.shop_reserve_coins,decision_context=dict(team=self.store.team_slot,
                    keywords=keywords,floor=state['floor_now'],
                    # Names, not the records: a record carries its own decision context, so
                    # embedding them made each purchase embed the last and the store passed
                    # the 2 MiB state guard after seven of them (live pi-20261014-082856
                    # could then no longer start: the loop raised on its own shop store).
                    owned_bought=[row.get('name') for row in state['shop_bought']],
                    wanted=list(shop['wanted']),
                    policy=settings.shop_policy,policy_trace=shop.get('policy_trace'),
                    reserve_coins=settings.shop_reserve_coins,refresh_limit=settings.shop_refreshes,
                    refreshes_used=state['shop_refreshes'],offers=shop['offers'],
                    why=(plan['detail'] or {}).get('why'),
                    carry_cap_coins=settings.shop_carry_cap_coins))
            elif plan['reason']=='refreshing_the_shelf_for_the_gift_the_plan_wants':
                target=shop_tx.reserve_refresh(self.run_id,visit,plan['detail']['cost'],shop['currency'],settings.shop_refreshes,frame_file(directory),reserve_coins=settings.shop_reserve_coins)
            else:
                target=shop_tx.reserve_confirm(self.run_id,visit,frame_file(directory))
            if list(target)!=list(plan['target']):
                raise ValueError('Shop transaction target differs from planned current control')
        if page=='GIFT_GET' and notice_ack is not None:
            if list(plan['target'])!=list(notice_ack):
                raise ValueError('Shop notice target differs from the acknowledged current control')
            # The acknowledgement is already durable and this note is the input's own
            # intent record: the notice is cleared once, and the receipt stays pending on
            # the returning shelf's exact coin delta plus removed offer.
            self.note('shop_notice_intent',page=page,target=list(notice_ack),
                      reason=plan['reason'],receipt_pending=True,
                      receipt_owner='returning_shelf_coin_delta_and_removed_offer')
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
            # Inert: when the click went out, and how many events preceded it. A later
            # round can ask `click_trace.classify` with these two numbers; nothing here
            # changes what gets clicked or when the run stops.
            self._clicked_at = time.monotonic()
            self._notes_at_click = self._note_count
            # The click a label can be earned from: this is where input actually goes
            # out. It used to be remembered only on the retry branch, so a run whose
            # clicks all worked recorded no click verdicts at all.
            if page == 'MAP':
                if superseded_click(state.get('map_pending'), plan['target']):
                    # Two clicks planned before one page settled would leave the first one
                    # unjudged, and an unjudged click cannot reach the refusal streak that
                    # decides a suspended exploration (3 intents produced 1 verdict live).
                    self._map_verdict( target=state['map_pending'], page=page,
                              outcome='rejected', frame=state.pop('map_click_frame', None),
                              reason='a_new_target_replaced_this_one_before_the_page_settled')
                    # A replaced click is still a click the game did not take, and the refusal
                    # streak is what decides an exploration was never resumed (live: a run that
                    # opened with `a_run_is_still_in_progress` made three node clicks and moved nothing).
                    state['map_refused_streak'] = int(state.get('map_refused_streak') or 0) + 1
                state['map_pending'] = list(plan['target'])
                # The verdict below is only diagnosable if it names the frame it judged;
                # `getattr(self, 'frames', None)` read nothing because that attribute lives
                # on the journal, not on the Runner, so every verdict carried frame=None.
                state['map_click_frame'] = (record.get('frame')
                                            or Path(frame_file(directory)).name)
            # Bracket the dispatch in a side channel.  A native crash (`access violation
            # reading 0xFFFFFFFFFFFFFFFF`, evidence/runtime/packaged-mirror-20261023-044354)
            # says nothing about which call died, and the maafw log for that run shows the
            # controller destroyed in the same second with no pipeline failure before it.
            # This cannot go through `note()`: `step()` returns the last noted event and
            # every caller reads it, so an extra event would change that contract (that is
            # exactly what `db6c9ba` reverted).  A file the run grows line by line keeps the
            # event stream intact and still survives a hard crash.
            def _bracket(phase):
                try:
                    with (Path(directory) / 'input-bracket.jsonl').open('a', encoding='utf-8') as handle:
                        handle.write(json.dumps(dict(phase=phase, page=page,
                                                     target=list(point),
                                                     reason=plan.get('reason')),
                                                ensure_ascii=False) + '\n')
                except OSError:
                    pass
            _bracket('begin')
            self.device.click(*point)
            _bracket('end')
        self.artifacts['clicks_sent'] += 1
        if plan.get('reason') in ('buying_the_gift_the_gift_plan_asked_for',
                                  'spending_the_coins_this_visit_would_carry_out_on_the_shelf'):
            # The price is booked as spent the moment the click goes out: a purchase
            # the shop answers with its own question is still a purchase this run has
            # committed the currency to, and the next shop frame must not offer it
            # again after a refresh brings the same name back.
            bought = dict((plan.get('detail') or {}), step=state['step'],
                          frame=frame_file(directory).name, point=None if point is None else list(point))
            self.note('shop_purchase_sent', gift=bought.get('name'), price=bought.get('price'),
                      why=bought.get('why'), currency=bought.get('currency'),
                      point=bought['point'],receipt_verified=False)
        elif plan.get('reason') == 'refreshing_the_shelf_for_the_gift_the_plan_wants':
            state['shop_refreshes']=shop_tx.refreshes_used(self.run_id,shop_tx.data['current_visit'])
            self.note('shop_shelf_refreshed', cost=(plan.get('detail') or {}).get('cost'),
                      refreshes_used=state['shop_refreshes'])
        elif plan.get('reason') == 'confirming_the_purchase_the_shop_asked_about':
            self.note('shop_purchase_confirmed', point=None if point is None else list(point))
        elif plan.get('reason') == 'the_gift_get_notice_is_cleared_with_its_own_confirm' and notice_ack is not None:
            # The notice's Confirm has gone out once.  The receipt is still unproven: only
            # the returning shelf's exact coin delta and complete offer list may clear it,
            # and no run state here may treat this click as payment.
            self.note('shop_notice_input_sent',target=list(notice_ack),receipt_pending=True,
                      receipt_owner='returning_shelf_coin_delta_and_removed_offer')
        if page == 'MAP' and plan.get('target') is not None:
            # Whether or not the click opened anything, that spot has had its turn:
            # live run build/window-run76.json opened the same gift tray eight times
            # because a click that did open something was never remembered.
            state['map_progress'].note_click(plan['target'])
            if state.get('map_pending') not in (None, list(plan['target'])):
                # Two clicks planned before one page settled would leave the first one
                # unjudged, and an unjudged click cannot reach the refusal streak that
                # decides a suspended exploration (3 intents produced 1 verdict live).
                self._map_verdict( target=state['map_pending'], page=page,
                          outcome='rejected', frame=state.pop('map_click_frame', None),
                          reason='a_new_target_replaced_this_one_before_the_page_settled')
                # A replaced click is still a click the game did not take, and the refusal
                # streak is what decides an exploration was never resumed (live: a run that
                # opened with `a_run_is_still_in_progress` made three node clicks and moved nothing).
                state['map_refused_streak'] = int(state.get('map_refused_streak') or 0) + 1
            state['map_pending'] = list(plan['target'])
            state['map_click_frame'] = (record.get('frame')
                                        or Path(frame_file(directory)).name)
        entry.update(click_point=None if point is None else list(point), delay_ms=delay)
        # Remember which of the two battle intents went out, so a page that comes back
        # with the same turn can be answered with the other one instead of a repeat.
        if page in ('BATTLE_HUD','BATTLE_PLANNING'):
            if plan.get('reason')=='start_button_submits_the_assigned_turn':
                state['battle_previous']='submit'
            elif str(plan.get('reason','')).endswith('_is_the_proven_auto_assign_control'):
                state['battle_previous']='assign'
        else:
            state['battle_previous']=None
        if plan.get('reason')=='start_button_submits_the_assigned_turn':
            # All twelve sinners can animate for longer than the ordinary page
            # read budget. Wait at most two minutes after the submitted turn;
            # this does not send another START or manufacture a HUD identity.
            state['turn_wait_until']=time.monotonic()+120
            # The page name cannot tell a submitted turn from an ignored one: the plan's
            # `expect` holds BATTLE_HUD, BATTLE_PLANNING and UNKNOWN, so the page coming
            # back looking like itself is "success" either way, and `advance` is False on
            # this plan so the swallowed-click detector at the end of this method can never
            # fire.  The HUD's own turn counter is the only fact that separates the two,
            # and it is read every frame, so remember it here and judge it on the next one.
            if submit_was_ignored(state.get('submit_turn'),record.get('turn'),
                    time.monotonic()-float(state.get('submit_turn_at') or 0)):
                # Submitting again from the same turn number is the measured stall: the
                # previous submit was ignored.  This sends nothing and changes no page; it
                # only makes the stall a recorded fact instead of a silent one.
                ignored=state.setdefault('submit_ignored',{})
                key=str(record.get('turn')).strip()
                ignored[key]=ignored.get(key,0)+1
                self.note('battle_submit_not_accepted',turn=record.get('turn'),
                          waited_s=round(time.monotonic()-float(state.get('submit_turn_at') or 0),1),
                          attempts=ignored[key],
                          reason='the_hud_turn_did_not_change_after_the_submit')
                if ignored[key]>=SUBMIT_IGNORED_ATTEMPTS:
                    # Three submits from one turn is not a slow animation: the board is
                    # refusing the click.  Stop feeding it and let the cell that watches
                    # for stalled progress take the page over, so this ends in a recovery
                    # attempt with a recorded cause instead of an unbounded re-click loop.
                    self.note('battle_submit_ignored_repeatedly',turn=record.get('turn'),
                              attempts=ignored[key],
                              reason='the_board_refused_three_submits_of_the_same_turn')
                    state['turn_wait_until']=0.0
            state['submit_turn']=record.get('turn')
            state['submit_turn_at']=time.monotonic()
        time.sleep(delay / 1000)
        settled, settled_page = None, None
        before_sha = record.get('image_sha256')
        # The floor theme pack is pulled down into the floor and the game answers with a
        # black loading frame before the map is drawn, so that one step reads its
        # successor on the unknown budget instead of the ordinary settle rounds. Live
        # evidence/runtime/window-20261012-021508: the drag was sent at 02:17:11 and
        # frame-0020 (02:17:13) is that empty frame with no text at all, while the next
        # live probe found the game already on MAP — so the run had stopped on a page
        # that was merely still loading.
        patient = plan.get('reason') == 'the_floor_theme_pack_is_pulled_down_to_be_taken'
        settle_budget = max(1, settings.unknown_rounds if patient else
                            min(6,settings.unknown_rounds) if page=='MAP' else settings.rounds)
        map_successor_reads=0
        for index in range(settle_budget):
            if index:
                time.sleep(settings.interval)
            settled = self._observe()
            settled_page = resolve_scene(self.registry, directory, settled)
            if page=='MAP' and settled_page in ('MAP','UNKNOWN'):
                # A fading map or hover animation is not an opened node.
                map_successor_reads=map_successor_reads+1 if settled_page=='MAP' else 0
                if map_successor_reads>=2:break  # Proven unchanged map: try another bounded candidate.
                continue
            if patient and settled_page=='MAP':
                from .theme_vision import ThemeCatalog
                header=map_header([Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])],settled.get('size') or (1920,1080))
                if not self.theme_transaction.matches(self.run_id,header,ThemeCatalog(ROOT/'assets/resource/base')):
                    self.note('theme_successor_read_retry',attempt=index+1,input_sent=False,
                              expected=self.theme_transaction.data['pending'])
                    continue
            if settled_page not in (page, 'UNKNOWN'):
                break
            # A tutorial card keeps the same page label but changes the pixels, so a
            # changed frame is the only evidence that the click landed.
            # Select can first show CONNECTING on the same gift offer. That pixel
            # change is not a named GET receipt; spend the remaining read-only
            # settle rounds without sending Select again.
            awaiting_gift_receipt = plan.get('reason') == 'select_takes_the_picked_floor_gifts'
            # The pixel rule is about the page the run came from keeping its label; a
            # changed frame on a page it cannot name is a page still loading, not a
            # landed successor, so waiting continues under the budget above (the floor
            # theme pull answers with exactly that empty frame).
            if (not awaiting_gift_receipt and not patient
                    and settled_page == page
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
        if page=='MAP' and settled_page=='UNKNOWN':
            entry.update(passed=False,reason='map_successor_unidentified_after_wait')
        if page=='STAR_GRACES' and (plan.get('detail') or {}).get('card') and transaction is not None:
            try:
                observed=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
                after_available=available_starlight(observed,settled.get('size') or (1920,1080))
                for attempt in range(1,4):
                    if after_available is not None or settled_page!='STAR_GRACES':break
                    self.note('grace_successor_balance_read_retry',attempt=attempt,input_sent=False,
                              pending_card=transaction.data['pending']['card'])
                    settled=self._observe();settled_page=settled.get('scene')
                    observed=[Text(t['text'],tuple(t['box']),t['score']) for t in settled.get('ocr',[])]
                    after_available=available_starlight(observed,settled.get('size') or (1920,1080))
                    entry.update(settled=settled,page_after=settled_page,scene_after=settled_page)
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
            # The press is proven by the notice page and its own name plate, not by the
            # plate agreeing with the run's picks: live run pi-20261014-072228 pressed
            # 'Select 2/2' for 'Prejudice'/'Uncapped Defibrilator' and the device answered
            # 'Dark Vestige'. The receipt stage keeps that name as a labelled substitution;
            # refusing it here is what stopped the run after the press had already landed.
            if not (settled_page=='GIFT_GET' and bool(title)
                    and self.floor_gift_transaction.notice_matches_a_pick(title)):
                entry.update(passed=False,reason='floor_gift_commit_receipt_not_proven',stopped='unverified_floor_gift_commit')
            elif not any(initial_gifts.same_name(title,n) for n in self.floor_gift_transaction.data['selected']):
                self.note('floor_gift_notice_outside_selection',printed=title,
                          selected=list(self.floor_gift_transaction.data['selected']),
                          successor=str(frame_file(directory)),input_sent=False)
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
                next_free,next_reward=self._receipt_successor_offers(settled,settled_page,directory)
                label=self.floor_gift_transaction.observe_receipt(settled_page,title,frame_file(directory),
                    next_free_offer=next_free,
                    next_reward_offer=next_reward)
                if label:
                    # The page answered the pick with a different gift. Keep what the
                    # device printed as a labelled observation instead of a silent guess.
                    self.note('floor_gift_receipt_substituted',expected=label['expected'],
                              printed=label['printed'],expected_owned=label['expected_owned'],
                              successor=label['proof'],input_sent=False)
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
                    size=settled.get('size') or (1920,1080)
                    from .party_vision import deployment_count
                    post_image,_=latest_frame(directory)
                    count=deployment_count(post_records,size,
                                           run_direct=getattr(self,'run_recognition_direct',None),
                                           image=post_image)
                    if count is None:
                        retry=self._unread_deployment_retry(state,page,plan.get('reason'))
                        if retry is not None:
                            return retry
                    self.deployment_transaction.observe(count)
                    state['deployment_read_attempts']=0
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
            # The player's own number of complete runs. This window keeps walking into the
            # next run -- every scope pays from its own budget -- until the launch has
            # delivered what it was asked for, and only then hands control back.
            reached = self._run_count_reached()
            if reached is not None:
                entry['reason'] = 'run_count_reached'
                entry['stopped'] = 'run_count_reached'
                entry['verified_runs'] = reached
                self.artifacts['run_count'] = reached
                self.note('run_count_reached', **reached)
                result = self._result(page, plan.get('target'), True, 'run_count_reached',
                                      done=True)
                # ``_result`` reads the last appended step, and this step's record is
                # appended after the ledger block, so the stop names itself here.
                result['reason'] = 'run_count_reached'
                result['verified_runs'] = reached
                return result
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
                if page=='MAP' and late_page=='UNKNOWN':
                    entry.update(passed=False,reason='map_successor_unidentified_after_wait')
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
            # A click whose plan declared `advance` with an ANY expectation has already
            # said that this input must change something: the page stays and the pixels
            # do not move, so the input was swallowed rather than merely early. On an
            # emulator the usual cause is an input channel that fell back to `adb shell
            # input tap` (the controller reports success and the game ignores the tap),
            # so the page is re-read and the plan retried a bounded number of times
            # instead of ending the whole run on the first swallowed tap.
            swallowed = (entry.get('reason') == 'unexpected_successor'
                         and plan.get('action') == CLICK
                         and plan.get('advance')
                         and ANY in (plan.get('expect') or [])
                         and plan.get('target') is not None
                         and state['swallowed_attempts'] + 1 < max(1, settings.page_tries))
            if swallowed:
                state['swallowed_attempts'] += 1
                entry['handled_retry']=True
                entry['stopped'] = 'click_was_swallowed_by_the_game'
                self.note('window_click_swallowed', page=page, target=list(plan['target']),
                          attempt=state['swallowed_attempts'], reason=plan.get('reason'),
                          input_helpers=self.input_helper_line())
                time.sleep(settings.interval)
                return self._result(page, plan.get('target'), True, None, waiting=True)
            retryable = (page == 'MAP' and settled_page in ('MAP', 'UNKNOWN')
                         and (plan.get('target') is not None or no_candidate)
                         and state['map_attempts'] + 1 < max(1, settings.map_tries))
            zoomed = (self._map_zoom_once(page, state, entry, plan)
                      if page == 'MAP' and settled_page in ('MAP', 'UNKNOWN') else None)
            if zoomed is not None:
                return zoomed
            # Count every attempt at this page, not only the ones that were allowed to
            # retry: with `map_tries: 1` the retry arm is unreachable, so counting inside
            # it left `map_attempts` at 0 forever and the ladder was the only consumer.
            state['map_attempts'] += 1
            if not retryable:
                recovered = self._recover(page, state, entry, plan)
                if recovered is not None:
                    return recovered
                entry['stopped'] = entry['reason']
                return self._result(page, plan.get('target'), True, entry['stopped'],
                                    done=True)
            entry['handled_retry']=True
            state['navigation_probe_pending']=True
            if no_candidate:
                # A frame with no candidate is not the same failure as a floor that
                # refused every click. Live evidence/runtime/packaged-mirror-
                # 20261021-202503 spent seven inputs on nodes the game never accepted
                # (ringed, chevron-marked and `?` nodes all left the page identical,
                # while the gear button at (1229,42) moved 228 435 pixels) and then
                # reported `no_candidate_node_observed`, which reads as "the reader
                # missed a node" when the truth was "the page would not step". Say
                # which one happened, so the next run does not chase the reader.
                entry['stopped'] = map_stop_reason(
                    tried=bool(state['map_progress'].tried),
                    attempts=state['map_attempts'])
                if entry['stopped'] == 'map_clicks_had_no_effect':
                    self.note('window_map_clicks_inert', page=page,
                              attempts=state['map_attempts'],
                              clicked=[list(box) for box in
                                       sorted(state['map_progress'].tried)])
                time.sleep(settings.interval)
                return self._result(page, plan.get('target'), True, None, waiting=True)
            # An unreachable node swallows the click and the page stays MAP, so skip it
            # and let the next candidate be tried in its place.
            state['map_progress'].note_click(plan['target'])
            entry['stopped'] = 'map_click_opened_no_panel'
            remaining = len([box for box in candidates
                             if tuple(box) != tuple(plan['target'])])
            self.note('window_map_retry', target=list(plan['target']),
                      attempt=state['map_attempts'], remaining=remaining)
            # This click is refuted by the game itself: the page never left MAP. Record
            # it as a labelled negative while the judgement is still local -- the 91 map
            # clicks in the archived runs left 79 of them with no verdict at all, and an
            # unlabelled click cannot teach a reader anything.
            self._map_verdict( target=list(plan['target']), page=page,
                      outcome='rejected',
                      frame=state.pop('map_click_frame', None),
                      kind=dict(plan.get('detail') or {}).get('kind'),
                      reason='the_page_stayed_on_the_map_after_the_click')
            # A refused click can mean two very different things, and the difference is
            # not visible in the frame: the candidate was wrong, or the exploration is
            # not resumed yet.  A controlled experiment on one device settled it --
            # before `entry -> Enter -> Dungeon Progress -> Resume` nine clicks moved
            # nothing (300..2000 px of animation only), and the first click after the
            # resume opened the node panel (107860 px).  So name the second case once a
            # streak of refusals has accumulated, instead of letting the run look like a
            # reader defect.
            map_refusal_streak(state, lambda event, **fields: self.note(event, page=page, **fields))
            # A refused click that will not be retried is a *stop* like any other, so it
            # spends the recovery ladder instead of handing control back to candidate
            # selection.  Measured on the recovery fixture without this: the rung sat at
            # 2 for eight consecutive steps (pinches 1, swipes 1) while the ladder has
            # six rungs, and the last four were never reached.
            if not remaining:
                recovered = self._recover(page, state, entry, plan)
                if recovered is not None:
                    return recovered
            return self._result(page, plan.get('target'), True, None, waiting=True)
        # A click the game did take: the page it was aimed at arrived. This is the only
        # positive label the loop can earn without being told the answer.
        if page != 'MAP' and state.get('map_pending'):
            self._map_verdict( target=state['map_pending'], page=page,
                      outcome='accepted',
                      frame=state.pop('map_click_frame', None),
                      reason='the_click_opened_the_next_page')
            state['map_refused_streak'] = 0
            state['map_pending'] = None
        # The other way a click is taken: the page stays MAP and the party walks. The
        # player's own point is the evidence -- it moves when the step is spent, and a
        # click the game refused leaves it exactly where it was.
        if map_dispatch.is_map(page) and state.get('map_pending'):
            # `player_of` takes a list of markers; handing it the single value
            # `player_marker` returns makes `player_readings` fail on `marker.node`
            # (an int, not a marker).  An empty list is the supported "no markers"
            # case and was measured to agree with the train reading on a live MAP
            # frame (evidence/runtime/packaged-mirror-20261022-063646/frame-0023:
            # both give (694,384)), so ask that way and keep the dot check honest.
            frame_image = latest_frame(directory)[0]
            here = party_point(frame_image)
            was = state.get('map_player')
            # A step is one lattice pitch, not any displacement: the reading can lock
            # onto a yellow HUD blob and jump ~900 px (frames 0023..0027 read (694,384)
            # in evidence/runtime/packaged-mirror-20261022-063646 while 0028..0032 read
            # (1616,82)), which a >20 px test would happily call a move.
            if here and was and one_step_from(here, was):
                self._map_verdict( target=state['map_pending'], page=page,
                          outcome='accepted',
                          frame=state.pop('map_click_frame', None),
                          reason='the_party_moved_after_the_click')
                state['map_pending'] = None
            # A reading that is not one lattice pitch from the last confirmed position is
            # not a step: on `packaged-mirror-20261023-060803` the locator answered
            # (703,316) for frames 0001-0005 and then (1052,439) from frame-0006 on -- a
            # 349 px jump in one click, because the brighter blob there is the fight
            # node's emblem, not the locomotive.  Adopting it made the adjacency filter
            # (and every later verdict) reason about a point that is not the party, so a
            # jump is refused and the confirmed position kept.
            if here and was and not one_step_from(here, was):
                # A jump is either a misread OR a view change, and refusing both traps
                # the run: `packaged-mirror-20261023-055547` read (703,316) then
                # (1052,439) with a *different badge set* around it (the camera moved),
                # and keeping the stale point made every later verdict reason about a
                # node the party had left.  The badges decide which of the two it is.
                marks = [list(pt) for pt in (gold_marks(frame_image) or [])]
                stored = state.get('map_view_marks')
                if stored and marks and movement_between(
                        dict(party=was, badges=stored),
                        dict(party=here, badges=marks)) == 'the_view_changed':
                    state['map_player'] = list(here)
                    state['map_view_marks'] = marks
                    self.note('map_view_changed', was=list(was), now=list(here),
                              reason='the_camera_moved_so_the_old_point_was_not_the_party')
                elif state.get('map_party_jump') != list(here):
                    state['map_party_jump'] = list(here)
                    self.note('map_party_jump_ignored', read=list(here),
                              kept=list(was),
                              reason='the_reading_is_not_one_lattice_step_away')
            elif here:
                state['map_player'] = list(here)
            if here:
                marks_now = [list(pt) for pt in (gold_marks(frame_image) or [])]
                if marks_now:
                    state['map_view_marks'] = marks_now
        if state.get('map_pending') is not None:
            # An intent with no verdict cannot teach a reader anything and cannot be
            # diagnosed later (the archived runs had 79 of 91 clicks in exactly this
            # state).  The click was made, the page settled, and neither "the party
            # moved" nor "a new control appeared" was true: record that, do not stay
            # silent.
            self._map_verdict( target=state['map_pending'], page=page,
                      outcome='rejected',
                      frame=state.pop('map_click_frame', None),
                      reason='the_map_stayed_with_the_party_in_place')
            state['map_pending'] = None
        state['map_attempts'] = 0
        map_dispatch.after_settle(state, page, settled_page)
        state['page_attempts'] = 0
        state['swallowed_attempts'] = 0
        # A refused click is a stop like any other: spend the next rung here, once,
        # for every recording site instead of at each of the four call sites.
        refused = state.pop('map_refused_since_progress', False)
        if refused and map_dispatch.is_map(page) and map_dispatch.is_map(settled_page):
            recovered = self._recover(page, state, entry, plan)
            if recovered is not None:
                return recovered
        # The rung is NOT cleared here: a step that returned without progress must
        # keep the ladder where it is, otherwise every round starts at rung 0 and a
        # six-rung ladder is spent one rung deep, forever.  `_recover` clears it when
        # the page itself changes, which is the only thing that counts as fresh.
        state['map_zoom_for'] = None
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
            # The guard may not end a run the ladder has not finished: the ladder is
            # the page's own recovery budget and it is per page, not per wording.
            spent = state.get('recovery_rung', 0) >= self._ladder_length(page)
            if (state['repeated_plans'][key] >= max(2, settings.loop_guard)
                    and spent):
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
        self._start_stall_watch()
        goal = max(0, int(steps))
        if goal == 0 and not settings.observe_only:
            goal = max(0, int(settings.steps))
        walked = 0
        while self.state['step'] < goal and walked < max(0, int(round_limit)):
            # The budget is a contract with the caller, not a hint: a step can block for
            # minutes inside the recogniser (live 420 s budget kept running to 610 s with
            # one 423.8 s gap between a click and the next event), so check here as well
            # as inside the step.
            if self.deadline is not None and time.monotonic() >= self.deadline:
                self._end_session('loop_deadline_exceeded',
                                  overshoot_s=round(time.monotonic() - self.deadline, 1))
                break
            if self.state.get('session_ended'):
                self.note('mirror_loop_stopped',
                          reason='the_pipeline_node_failed_before_the_next_input',
                          steps=self.state['step'], clicks=self.artifacts['clicks_sent'])
                break
            # A heartbeat before each step: the process can die natively inside a step
            # and write nothing, so 22 of 107 retained runs end on their last business
            # event with no cause (`tools/audit_runs.py`).  This line makes the last
            # thing the run started the thing the log reports.
            # Observe only: what the last click left behind.  Nothing stops on this
            # yet; the field exists so a live run can show whether it ever fires.
            _clicked = getattr(self, '_clicked_at', None)
            _verdict = click_trace.classify(
                seconds_since_click=(time.monotonic() - _clicked) if _clicked is not None else None,
                heartbeat_seen=(_clicked is not None
                                and self._note_count > getattr(self, '_notes_at_click', 0)),
                page=self.state.get('page') or getattr(self, '_last_page', None))
            self.note('loop_heartbeat', step=self.state['step'],
                      phase='step_start',
                      page=self.state.get('page') or getattr(self, '_last_page', None),
                      build=_build_id(), trace_verdict=_verdict['kind'])
            started_step = time.monotonic()
            try:
                result = self.step()
                blocked = time.monotonic() - started_step
                if blocked > DEEP_STEP_SECONDS:
                    # Names the block the budget cannot interrupt: next time this fires,
                    # the number is the evidence for which Maa node to bound.
                    self.note('step_outlived_its_window', seconds=round(blocked, 1),
                              page=self.state.get('page') or getattr(self, '_last_page', None))
            except (RuntimeError, OSError) as error:
                # One end, one reason: the deadline the caller set outranks a failure that
                # is only its symptom, and the loop must stop rather than end twice.
                overdue = self.deadline is not None and time.monotonic() >= self.deadline
                named = getattr(error, 'reason', None)
                self._end_session(named or ('loop_deadline_exceeded' if overdue
                                            else 'the_task_raised_before_the_next_input'),
                                  error=str(error)[:300])
                break
            # A step that only waits is a real iteration and must be counted: a live
            # run once waited 421 s on RESUME_DIALOG while writing nothing, so the
            # progress watchdog, not the loop, was the only thing that noticed.
            if result.get('waiting'):
                self._waited = getattr(self, '_waited', 0) + 1
                decision = wait_decision(self._waited)
                if decision['note']:
                    self.note('loop_waited', page=result.get('page'),
                              waited=self._waited, reason=decision['reason'])
                if decision['stop']:
                    self._end_session(decision['reason'], waited=self._waited)
                    break
            else:
                self._waited = 0
                walked += 1
            if result.get('done'):
                break
            time.sleep(interval)
        return self.summary()

    # -- records -----------------------------------------------------------
    def _explore_unknown(self,record,frame,candidates):
        """Try independently read navigation controls, never unresolved payments."""
        explorer=self.exploration
        if explorer is None:return None
        active=self.store.data.get('active') or {}
        transactions=(self.grace_transaction,self.initial_transaction,
                      self.deployment_transaction,self.theme_transaction,
                      self.floor_gift_transaction,self.shop_transaction)
        if active.get('victory') or active.get('phase')=='entry_pending' or any(
                tx and any((tx.data or {}).get(k) for k in ('pending','receipt_pending','submit_pending'))
                for tx in transactions):
            self.note('unknown_exploration_waits_for_existing_transaction',input_sent=False)
            return None
        candidate=explorer.choose(record)
        if candidate is None:return None
        box=candidate['box'];x,y,w,h=box
        point=(random.randint(x+w//4,x+max(w//4,w*3//4-1)),
               random.randint(y+h//4,y+max(h//4,h*3//4-1)))
        delay=random.randint(350,750)
        end=None
        if candidate.get('action')=='swipe':
            ex,ey,ew,eh=candidate['to_box'];end=(random.randint(ex+ew//4,ex+ew*3//4),random.randint(ey+eh//4,ey+eh*3//4))
        explorer.reserve(frame_file(self.directory),candidate,point,delay,end)
        self.note('unknown_exploration_intent',candidate=candidate,point=list(point),end=end,delay_ms=delay)
        entry=dict(step=self.state['step'],page_before=record['scene'],scene_before=record['scene'],
            observation=record,frame=frame,candidates=candidates,action=candidate.get('action','click'),
            target=box,click_point=list(point),delay_ms=delay,clicks_sent=1,
            passed=False,stopped=None,reason='unknown_navigation_probe')
        self.artifacts['steps'].append(entry)
        self.artifacts['clicks_sent']+=1;self.state['step']+=1
        # Attempt counts and intent are durable before Maa receives any input.
        if end is not None:self.device.swipe(*point,*end,delay)
        else:self.device.click(*point)
        time.sleep(delay/1000)
        after=record;page='UNKNOWN'
        for attempt in range(max(1,self.settings.rounds)):
            if attempt:time.sleep(self.settings.interval)
            after=self._observe();page=resolve_scene(self.registry,self.directory,after)
            if page not in WAIT_PAGES:break
        outcome=explorer.finish(frame_file(self.directory),page)
        self.note('unknown_exploration_review_queued',**outcome,input_sent=False)
        entry.update(page_after=page,settled=after,passed=True,
            progress_verified=outcome['success'],review_proposal=outcome['proposal'],
            reason='unknown_navigation_succeeded' if outcome['success'] else 'unknown_navigation_unresolved')
        return self._result(record['scene'],box,True,None)

    def _receipt_successor_offers(self,record,page,directory):
        """The fresh offers that prove a floor-gift receipt's successor on this page.

        Both the settling path and the retained-evidence recovery path read the same
        page through here, because a proof one of them accepts and the other does not
        is how a cleared notice leaves a receipt that can never be booked.
        """
        next_free=None
        if page=='GIFT_PICK':
            from .floor_gifts import observe as observe_gifts
            records=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
            offers,count=observe_gifts(records,record.get('size') or (1920,1080),self.floor_gift_catalog,
                image=latest_frame(directory)[0],select_box=self.controls.get('gift_pick.select_button'))
            if (count==dict(chosen=0,required=1) and offers
                    and all(o.selection_source.endswith('_free_select_button') for o in offers)):
                next_free=dict(count=count,source=offers[0].selection_source,
                    offer=self.floor_gift_transaction.signature(offers))
        next_reward=unselected_reward_successor(record) if page=='REWARD_CARD' else None
        return next_free,next_reward

    def _resolve_floor_receipt(self,floor_tx,page,name,directory,record=None):
        """Book an outstanding floor-gift receipt from retained evidence.

        Never re-sends input: the booked notice's own frame is re-read and its image
        hash checked, so the resolution rests on what the device already produced.
        The successor page has to prove itself the same way the settling path reads
        it; the recovery path is not a weaker rule, it is the same rule over a frame
        the run no longer has in hand.
        """
        from . import initial_gifts
        from .floor_gift_transaction import retained_notice_name
        if record is None:return False
        pending=floor_tx.data.get('pending') or {}
        try:
            retained=retained_notice_name(pending['proof'],Path(directory).parent)
        except (ValueError,KeyError,TypeError,FileNotFoundError,OSError):
            return False
        if not retained or not initial_gifts.same_name(retained,pending['title']):return False
        next_free,next_reward=self._receipt_successor_offers(record,page,directory)
        try:
            label=floor_tx.observe_receipt(page,name,frame_file(directory),
                next_free_offer=next_free,next_reward_offer=next_reward)
        except ValueError:
            return False
        self.note('floor_gift_receipt_recovered',title=pending['title'],before=str(pending['proof']),
                  successor=str(frame_file(directory)),printed=name,substituted=label)
        return True

    def _record(self, page, record, frame, candidates, plan, reason):
        """Append the record-only step the guard paths write, and return its stop."""
        self.artifacts['steps'].append({
            'step': self.state['step'], 'page_before': page, 'scene_before': record['scene'],
            'frame': frame, 'observation': record, 'plan': plan,
            'candidates': candidates, 'action': 'record', 'reason': reason,
            'passed': False, 'clicks_sent': 0, 'stopped': reason})
        return reason

    def _detail(self, **detail):
        """Attach the numbers the reason needs to the step just recorded.

        The reasons that stop a run are mostly counts -- what was asked for, what was
        bought, what the page offered -- and a person reading the log has no other way
        to see them: the step is a record-only step with no plan of its own.
        """
        if self.artifacts['steps']:
            self.artifacts['steps'][-1].setdefault('detail', {}).update(detail)

    def _unread_grace_retry(self, state, page, reason):
        """Wait out a Grace page whose own reading did not prove this frame.

        The counter and the prices are re-read from the newest frame on every round, so
        a reading that fails describes one frame rather than the page: the live run that
        stopped on 'configured_grace_costs_not_proven' read card 4's price twice in the
        frame taken right after the purchase that re-rendered it, while the frame before
        and the frame seven rounds later both read it once
        (evidence/runtime/window-20261012-015054/frame-0005.json against frame-0003 and
        frame-0007). page_tries bounds the wait, and the round that gives up still stops
        with the same reason on the record.
        """
        if state['grace_read_attempts'] + 1 >= max(1, self.settings.page_tries):
            return None
        state['grace_read_attempts'] += 1
        self.note('grace_page_reread', page=page, attempt=state['grace_read_attempts'],
                  reason=reason, input_helpers=self.input_helper_line())
        time.sleep(self.settings.interval)
        return self._result(page, None, False, None, waiting=True)

    def _unread_deployment_retry(self, state, page, reason):
        """Wait out a participant counter this frame did not carry.

        The page's own counter rolls up while it changes and the settled frame can be
        read without it at all: live evidence/runtime/window-20261012-022454/frame-0026
        is a PRE_BATTLE_TEAM frame whose counter band held only the 'Chai' label under
        it, while the frames either side read 7/12, so the run stopped on 'Deployment
        successor participant count not proven' although its click had landed. Re-reading
        sends nothing, and page_tries bounds it; the round that gives up still stops with
        the reason the log has always shown.
        """
        if state['deployment_read_attempts'] + 1 >= max(1, self.settings.page_tries):
            return None
        state['deployment_read_attempts'] += 1
        self.note('deployment_counter_reread', page=page,
                  attempt=state['deployment_read_attempts'], reason=reason,
                  input_helpers=self.input_helper_line())
        time.sleep(self.settings.interval)
        return self._result(page, None, False, None, waiting=True)

    def _map_zoom_once(self, page, state, entry, plan):
        """Move the map view before spending another candidate node.

        A map click that leaves the page exactly where it was means the node the plan
        aimed at was not on screen: live run pi-20261015-200848 clicked five candidates
        in ninety seconds with ``Exploring Floor 3`` never changing, because the map was
        still zoomed in on the panel it had opened. The map's own remedy -- a pinch-out,
        the first rung of :data:`RECOVERY_LADDER` -- is therefore spent once per stalled
        click, before the next candidate is tried, instead of only after every candidate
        has failed. Nothing is clicked, so it stays safe on a view the reader cannot
        classify yet.
        """
        signature = str(page)
        if state.get('map_zoom_for') == signature:
            return None
        state['map_zoom_for'] = signature
        # The pinch *is* the ladder's first rung; booking it here keeps the ladder from
        # spending it a second time on the same stop and lets the later rungs follow.
        state['recovery_for'] = signature
        state['recovery_rung'] = 1
        entry['handled_retry'] = True
        entry['stopped'] = 'the_map_view_is_pinched_out_before_another_candidate'
        self.note('window_recovery', page=page, gesture='pinch_out', rung=0,
                  before_another_candidate=True, input_helpers=self.input_helper_line(),
                  **self._recovery_fields(entry, plan))
        self._recovery_gesture('pinch_out')
        time.sleep(self.settings.interval)
        return self._result(page, plan.get('target'), True, None, waiting=True)

    def _recovery_fields(self, entry, plan):
        """Every field a `window_recovery` event carries, computed in one place.

        There are two producers of that event (the pinch-the-map-first path and the
        ladder path).  Each one used to assemble its own kwargs, so a field added to
        one was silently absent from the other -- measured on
        `evidence/runtime/packaged-mirror-20261023-085334`, where the pinch path wrote
        a recovery with no `refused_kind` at all.  Recording and deciding stay
        separate on purpose: the recorded kind may be read from any of the three
        names, the deciding kind stays on the strictest one.
        """
        recorded = kind_of(reason=entry.get('reason'),
                           stopped_reason=entry.get('stopped_reason') or entry.get('reason'),
                           plan_reason=plan.get('reason'))
        deciding = REFUSALS.get(entry.get('reason'))
        return dict(refused_kind=recorded, recovery_action=recovery_for(recorded),
                    build=_build_id(),
                    deciding_kind=deciding, stopped_reason=entry.get('stopped_reason') or entry.get('reason'),
                    plan_reason=plan.get('reason'))

    def _recovery_gesture(self, name):
        """Send one gesture that moves the view and presses no game control."""
        if name == 'pinch_out':
            self.device.pinch(MAP_ZOOM_OUT['centre'], MAP_ZOOM_OUT['radius'],
                              MAP_ZOOM_OUT['factor'], MAP_ZOOM_OUT['seconds'])
        elif name == 'drag_down':
            self.device.swipe(RECOVERY_DRAG[0], RECOVERY_DRAG[1],
                              RECOVERY_DRAG[2], RECOVERY_DRAG[3], 400)
        elif name == 'drag_up':
            self.device.swipe(RECOVERY_DRAG[2], RECOVERY_DRAG[3],
                              RECOVERY_DRAG[0], RECOVERY_DRAG[1], 400)
        elif name == 'pan_left':
            self.device.swipe(RECOVERY_PAN[0], RECOVERY_PAN[1],
                              RECOVERY_PAN[2], RECOVERY_PAN[3], 400)
        elif name == 'pan_right':
            self.device.swipe(RECOVERY_PAN[2], RECOVERY_PAN[3],
                              RECOVERY_PAN[0], RECOVERY_PAN[1], 400)
        else:
            time.sleep(1.5)
        # A gesture is not a click: ``clicks_sent`` keeps counting the taps that were
        # aimed at something, and the recovery is counted on its own.
        self.artifacts['recoveries'] = self.artifacts.get('recoveries', 0) + 1

    def _recover(self, page, state, entry, plan):
        """Spend the next recovery rung instead of ending the run; ``None`` when spent.

        The live runs of 2026-10-15 stopped on one page shape after another -- a
        purchase dialog whose badge the reader could not balance, a zoomed-in floor
        whose nodes were off screen, a skill check whose strip had not faded in, a
        shop whose offer never became the one the plan was waiting for. Each of them
        was a *view* that a gesture moves, so a step that did not land no longer ends
        the run by itself: the page first gets the same ladder of viewport gestures,
        one rung per stop, and only a stop that has already spent the whole ladder
        ends the run. No rung presses a game control, which is what makes the ladder
        safe to try on a page whose layout is unknown yet.
        """
        # Identity of a *stop*, not of the wording it arrived with.  Keying on the
        # reason made the ladder unspendable: the reason changes between rounds
        # (`no_candidate_node_observed`, then a click verdict, then the loop guard),
        # so the signature changed and the rung went back to 0.  Measured on the
        # recovery fixture -- rungs spent 1, 2, then 0, 0 and the run ended with
        # `the_same_plan_repeated` while four rungs were still unspent.
        signature = str(page)
        if state.get('recovery_for') != signature:
            state['recovery_for'] = signature
            state['recovery_rung'] = 0
        raw = self.settings.get('recovery_tries')
        ladder = RECOVERY_LADDER[:(len(RECOVERY_LADDER) if raw is None
                                   else max(0, int(raw)))]
        if str(page) in FIXED_LAYOUT_PAGES:
            # A fixed screen has no view to move: pinching it proved to kill the task
            # (2026-10-22 00:09 run, access violation right after rung 0 on DRIVE), so
            # those pages get the settle wait and nothing that drags or pinches.
            ladder = tuple(entry for entry in ladder if entry[0] == 'wait')
        # The refusal's reason is not always `entry['reason']`: the pinch path of the
        # same ladder names it `stopped_reason`, and the plan carries `plan_reason`.
        # Reading only `reason` left every historical recovery event with a null
        # kind (0 of 181 events carried `refused_kind`), so the table below never
        # decided anything and the full six-rung ladder was always spent.
        refused_reason = (entry.get('reason') or entry.get('stopped_reason')
                          or entry.get('plan_reason'))
        # Recording and deciding are deliberately separate: the kind *recorded* may be
        # read from any of the three names so the audit can see what happened, while the
        # kind that *narrows the ladder* stays on the strictest source (`reason`) until a
        # narrowing is proven offline -- otherwise a recording fix silently changes which
        # gestures run.
        recorded_kind = self._recovery_fields(entry, plan)['refused_kind']
        deciding_kind = REFUSALS.get(entry.get('reason'))
        ladder = ladder_for(recovery_for(deciding_kind), ladder)
        rung = state['recovery_rung']
        if rung >= len(ladder):
            # The exhausted ladder is the outcome of the same decision, so it carries
            # the same recorded kind: otherwise the one case where the engine gave up
            # is the one case the audit cannot classify.
            self.note('window_recovery_exhausted', page=page, reason=entry.get('reason'),
                      rungs=[name for name, _ in ladder],
                      input_helpers=self.input_helper_line(),
                      **self._recovery_fields(entry, plan))
            return None
        name, why = ladder[rung]
        state['recovery_rung'] = rung + 1
        entry['handled_retry'] = True
        entry['stopped'] = why
        # The refusal's *kind* decides what the engine may do next; recording it here
        # makes the decision inspectable while the gesture set is still the shared
        # ladder.  `recovery_for` is the single table that will drive the choice.
        self.note('window_recovery', page=page, gesture=name, rung=rung,
                  **self._recovery_fields(entry, plan),
                  input_helpers=self.input_helper_line())
        self._recovery_gesture(name)
        time.sleep(self.settings.interval)
        return self._result(page, plan.get('target'), True, None, waiting=True)

    def _ladder_length(self, page):
        """How many rungs this page is allowed, matching :meth:`_recover` exactly."""
        raw = self.settings.get('recovery_tries')
        length = len(RECOVERY_LADDER) if raw is None else max(0, int(raw))
        if str(page) in FIXED_LAYOUT_PAGES:
            length = min(length, 1)
        return length

    PROGRESS_SECONDS = 900.0
    STALL_SECONDS = 300.0
    """How long the loop may go without a new frame before the process ends itself."""

    def _end_session(self, reason, **detail):
        """Record that the task this loop runs inside is gone.

        A failed pipeline node takes the controller down with it, so every later
        input would post through a released pointer.  The window says so once and
        then stops instead of clicking into a dead session.
        """
        if self.state.get('session_ended'):
            return False
        self.state['session_ended'] = str(reason)
        device = getattr(self, 'device', None)
        if hasattr(device, 'end_session'):
            device.end_session(reason)
        self.note('mirror_session_ended', reason=str(reason), **detail)
        return True

    def _start_stall_watch(self):
        """Watch the frame heartbeat so a wedged recognition ends the run loudly.

        No gesture recovers a call that never returns, so the loop is watched from
        outside it: a daemon thread ends the process once no frame has arrived for
        ``settings.stall_seconds``, and leaves the record of where it stopped in the
        run's own directory first.
        """
        raw = self.settings.get('stall_seconds')
        limit = self.STALL_SECONDS if raw is None else float(raw)
        if limit <= 0 or getattr(self, '_stall_watch', None) is not None:
            return None
        self.artifacts['heartbeat'] = time.monotonic()
        watch = threading.Thread(
            target=stall_watchdog, name='maalimbus-stall', daemon=True,
            args=(lambda: self.artifacts.get('heartbeat', 0.0),),
            kwargs={'limit': limit,
                    'on_stall': lambda probe_changed=None: self._record_stall(
                        limit, probe_changed=probe_changed),
                    'probe': self._screen_answers_a_reread})
        watch.start()
        self._stall_watch = watch
        # The frame watchdog only catches a recognition call that never returns.
        # A loop that observes happily and journals nothing is the other wedge, so
        # it gets its own watch over the newest event rather than the newest frame.
        raw_progress = self.settings.get('progress_seconds')
        progress = self.PROGRESS_SECONDS if raw_progress is None else float(raw_progress)
        # One live run was given 450 s and took 1058 s because this watch outlived the
        # budget by 2.5x.  A watchdog may never be longer than the run it protects.
        configured = progress
        progress = bounded_limit(progress, getattr(self, 'deadline', None))
        # Once the window was shortened because the run's own budget is running out,
        # a grace window would push the run past that budget again (live 420 s budget
        # took 608.9 s: the watch fired on time, then bought up to two more windows).
        # A clamped watch never asks for grace.
        clamped = progress != configured
        if clamped:
            def on_stall():
                record = self._record_no_progress(progress) or {}
                record['stillness_action'] = 'stop'
                return record
        else:
            on_stall = lambda: self._record_no_progress(progress)
        if progress > 0:
            self.artifacts.setdefault('event_heartbeat', time.monotonic())
            self._progress_watch = threading.Thread(
                target=stall_watchdog, name='maalimbus-progress', daemon=True,
                args=(lambda: self.artifacts.get('event_heartbeat', 0.0),),
                kwargs={'limit': progress, 'on_stall': on_stall})
            self._progress_watch.start()
        return watch

    def _screen_answers_a_reread(self):
        """Re-read the current screen once and say whether anything changed."""
        try:
            first = self.device.screencap() if hasattr(self.device, 'screencap') else None
        except Exception:
            return None
        if first is None:
            return None
        time.sleep(1.5)
        try:
            second = self.device.screencap() if hasattr(self.device, 'screencap') else None
        except Exception:
            return None
        if second is None:
            return None
        return bytes(first) != bytes(second)

    def _record_stall(self, limit, *, probe_changed=None):
        """Leave the evidence of the wedge before the process ends itself."""
        heartbeat = self.artifacts.get('heartbeat', 0.0)
        # Name the stillness before acting on it.  With no probe available this is
        # `frozen_page`, which keeps today's behaviour (stop) while recording which of
        # the five kinds the evidence actually supports -- so the next live stop is a
        # lookup, not an investigation.
        from . import stillness as _stillness
        _age = round(time.monotonic() - heartbeat, 1)
        _verdict = _stillness.classify(still_seconds=_age, limit=limit,
                                       page=self.state.get('page'),
                                       probe_changed=probe_changed,
                                       last_event=self.last_event)
        record = {'reason': _verdict['reason'],
                  'stillness_kind': _verdict['kind'],
                  'stillness_action': _verdict['action'],
                  'limit_seconds': limit,
                  'heartbeat_age_seconds': round(time.monotonic() - heartbeat, 1),
                  'step': self.state.get('step'), 'page': self.state.get('page'),
                  'last_event': self.last_event,
                  'steps_recorded': len(self.artifacts.get('steps', []))}
        try:
            # The event carried only the heartbeat age, so every diagnosis of this stop
            # had to re-read the whole journal to learn which page and which intent it
            # died on (`packaged-mirror-20261023-060803`: the answer was RESUME_DIALOG and
            # `resume_rejoins_the_run_that_is_already_in_progress`).  The record already
            # knew both; the event did not say.
            self.note('window_stall', reason=record['reason'],
                      limit_seconds=record['limit_seconds'],
                      heartbeat_age=record['heartbeat_age_seconds'],
                      step=record['step'], page=record['page'],
                      last_event=record['last_event'],
                      stillness_kind=record['stillness_kind'],
                      stillness_action=record['stillness_action'])
            # The watchdog ends the process with `os._exit(4)`, so the loop's normal
            # `mirror_loop_stopped` never runs and the run reads as a silent death to
            # `tools/audit_silent.py` -- 4 of 23 silent runs ended exactly here, on a
            # `window_stall` with no stop event.  Write the stop before the exit: the
            # canonical record of why a run ended must not depend on which path ended it.
            self.note('mirror_loop_stopped', reason=record['reason'],
                      stop_path='stall_watchdog', step=record['step'],
                      page=record['page'], last_event=record['last_event'])
        except Exception:  # pragma: no cover - a journal may be closing
            pass
        try:
            (Path(self.directory) / 'agent-stall.json').write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:  # pragma: no cover - the directory may be gone
            pass
        return record

    def _record_no_progress(self, limit):
        """Leave the record of a loop that kept looking and stopped moving."""
        heartbeat = self.artifacts.get('event_heartbeat', 0.0)
        record = {'reason': 'the_run_kept_observing_without_writing_anything',
                  'limit_seconds': limit,
                  'event_age_seconds': round(time.monotonic() - heartbeat, 1),
                  'step': self.state.get('step'), 'page': self.state.get('page'),
                  'last_event': self.last_event}
        try:
            self.note('window_no_progress', reason=record['reason'],
                      limit_seconds=record['limit_seconds'],
                      event_age=record['event_age_seconds'], step=record['step'])
        except Exception:  # pragma: no cover - a journal may be closing
            pass
        try:
            (Path(self.directory) / 'agent-no-progress.json').write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:  # pragma: no cover
            pass
        return record

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
        result['decisions'] = self.artifacts.get('decisions',[])
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
        ended = self.state.get('session_ended')
        result['passed'] = (all(entry['passed'] or entry.get('handled_retry') for entry in result['steps'])
                            and bool(result['steps'] or flow_records)
                            and not self.state.get('navigation_probe_pending')
                            and failed_flow is None
                            and not ended)
        # A session the task killed is never a pass, however clean its step records
        # look: the run stopped where the game did, not where the plan finished.
        result['reason'] = (str(ended) if ended else 'window_steps_passed' if result['passed']
                            else ((failed_flow or {}).get('reason')
                                  or (last or {}).get('stopped')
                                  or (last or {}).get('reason')
                                  or ('navigation_probe_unresolved_at_boundary' if self.state.get('navigation_probe_pending') else 'no_step_recorded')))
        if self.store is not None:
            # The one place a verified-run count is visible to the caller and the log:
            # what this launch asked for, what it delivered, and the ledger's own total.
            result['verified_runs'] = dict(target=int(settings.run_count or 0),
                                           completed=self._verified_runs(),
                                           ledger_total=_completed_runs(self.store),
                                           counted_at_launch=self.run_baseline)
        return result


def _completed_runs(store):
    """The ledger's all-time verified-run total, or 0 when it cannot be read."""
    try:
        return int((store.data or {}).get('completed_runs') or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


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
            'recovery_for': None, 'recovery_rung': 0, 'map_zoom_for': None,
            'page_attempts': 0, 'gift_picks': 0, 'initial_picked': 0,
            'swallowed_attempts': 0, 'grace_read_attempts': 0, 'deployment_read_attempts': 0,
            'shop_bought': [], 'shop_refreshes': 0,
            'repeated_plans': {}, 'guard_page': None, 'claim_steps': 0,
            'team_slot_picked': None, 'defeat_row_sent': False, 'defeat_attempts': 0,
            'identity_sha': None, 'session_ended': None,
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


# How many consecutive waiting steps are tolerated before the loop ends itself.
WAIT_LIMIT = 40


def wait_decision(waited, *, limit=WAIT_LIMIT):
    """What a waiting step does: report every fifth, end once the limit is passed.

    Extracted so the rule can be tested without building a frame sequence that
    never changes page: the behaviour is a decision, not a side effect.
    """
    if waited > limit:
        return {'note': True, 'stop': True,
                'reason': 'the_loop_waited_without_a_new_page'}
    return {'note': waited % 5 == 0, 'stop': False,
            'reason': 'a_waiting_step_is_still_a_step'}


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
    parser.add_argument('--battle-assignment',choices=('win_rate','damage','observe'),
                        default=defaults['battle_assignment'],help='Proven battle auto-assignment control or stop without battle input')
    parser.add_argument('--gift-search', choices=('refuse', 'select'),
                        default=defaults['gift_search'],
                        help='what to do on the gift-search page')
    parser.add_argument('--shop-refreshes', type=int, default=defaults['shop_refreshes'],
                        help='how many plain shelf refreshes one shop visit may pay for')
    parser.add_argument('--shop-policy',choices=('manual','learned'),default=defaults['shop_policy'],
                        help='rules or observed shelf-yield learning, always within player caps')
    parser.add_argument('--shop-reserve-coins',type=int,default=defaults['shop_reserve_coins'],
                        help='minimum run coins preserved after purchases and refreshes')
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


def _build_id():
    """The commit this app was frozen from, or None when it cannot be read.

    A recovery recorded without it cannot be compared against a fix: the audit read
    196 recoveries with `named: 0` and called the decision table dead, when every one
    of them predated the recorder (`frozen build: 5973462a`).  Recording the build
    beside the decision makes "0 named" mean one thing only.
    """
    import json
    for candidate in (ROOT / 'build-info.json', ROOT / 'dist' / 'MaaLimbus' / 'build-info.json'):
        try:
            return json.loads(candidate.read_text(encoding='utf-8')).get('source_commit')
        except (OSError, ValueError):
            continue
    return None
