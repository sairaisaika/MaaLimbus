"""One bounded window: walk the live dungeon loop and record every page it meets.

This is the verification-window engine. A window is one continuous live session
that advances the run through the pages the script must recognise, records each
page (frame + full OCR + scene + the controls read from that page), and stops the
moment it meets a page it cannot prove.

Rules:
  * exactly one input per step, chosen by ``maalimbus.window.plan_step``;
  * the point is sampled inside an inset of the planned box with a bounded delay;
  * the successor page must be one of the expected pages, otherwise the step is
    recorded as ``unexpected_successor`` and the window stops;
  * a page with no proven control is recorded and the window stops (never guessed);
  * ``--observe-only`` sends no input at all.

The gate is the same as the other live tools: ``build/map-probe-authorization.json``
must grant ``live_input_authorized`` for the nonce passed on the command line.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import random
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'agent'))

import cv2
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maalimbus import anchors
from maalimbus.adb_device import build, discover, foreground_of, input_policy, pin_input
from maalimbus.controller_lease import ControllerLease
from maalimbus.event_vision import choice_options, gift_hints, preferred_choice
from maalimbus.jobs import wait_job, wait_task
from maalimbus.map_vision import (NODE_BADGE_TEMPLATE, map_clicks)
from maalimbus.overlay_vision import carousel_dots, page_turn_arrows
from maalimbus.reward_vision import (GIFT_COUNTER_BAND, counter_state,
                                     gift_cards, select_ready)
from maalimbus.team_vision import CARD_COUNT, card_states
from maalimbus.vision import Text, inset_box
from maalimbus.window import (NODE, SWIPE, plan_step, resolve_overlay,
                              step_result)
from recognition import (BattleObservation, Journal, LimbusRecognition,
                         MapObservation)

AUTHORIZATION = ROOT / 'build/map-probe-authorization.json'
REGISTRY = ROOT / 'assets/resource/base/anchors.json'
#: pages the loop guard never counts against: the guide book advances card by card
#: from the same control, and a battle legitimately alternates Win Rate and START.
LOOP_GUARD_EXEMPT = ('TUTORIAL', 'BATTLE_HUD', 'BATTLE_PLANNING')
PIPELINE_DIR = ROOT / 'build/window-debug'
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


def prepare() -> Path:
    (PIPELINE_DIR / 'pipeline').mkdir(parents=True, exist_ok=True)
    (PIPELINE_DIR / 'pipeline/window.json').write_text(
        json.dumps(PIPELINE, indent=2) + '\n', encoding='utf-8')
    return PIPELINE_DIR


def authorized(nonce: str) -> bool:
    if not AUTHORIZATION.is_file():
        return False
    data = json.loads(AUTHORIZATION.read_text(encoding='utf-8'))
    return (data.get('live_input_authorized') is True and bool(data.get('nonce'))
            and data['nonce'] == nonce)


def controls_by_id(registry: dict) -> dict:
    """Anchor name -> proven pixel box, from the anchors registry."""
    controls = {}
    for page in registry.get('pages', []):
        for control in page.get('controls', []):
            box = (control.get('verified_on') or {}).get('box')
            if box is not None:
                controls[control['id']] = list(box)
    return controls


def run_node(tasker, name, deadline):
    job = tasker.post_task(name)
    try:
        return wait_task(tasker, job, deadline=deadline)
    except RuntimeError as error:
        if not job.done:
            wait_job(tasker.post_stop(), timeout=5)
        return {'task_succeeded': False, 'stop_confirmed': job.done, 'error': str(error)}


def events(directory, name):
    return [json.loads(line) for line in
            (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()
            if json.loads(line).get('event') == name]


def latest_frame(directory):
    for path in sorted(directory.glob('frame-*.png'), reverse=True):
        image = cv2.imread(str(path))
        if image is not None:
            return image, path.name
    return None, None


def frame_sha(directory):
    """The sha256 the journal recorded for the newest stored frame.

    A frame is only stored when the pixels change, so the newest frame's hash is
    the identity of the screen just observed.
    """
    for path in sorted(directory.glob('frame-*.json'), reverse=True):
        try:
            sha = json.loads(path.read_text(encoding='utf-8')).get('image_sha256')
        except (OSError, ValueError):
            continue
        if sha:
            return sha
    return None


def frame_details(directory):
    """The newest stored frame's ``ocr`` tokens and ``size``, or ``None``.

    The analyze event carries only semantic fields (scene, floor, pack, boxes), so
    the token list and frame size that the guide-book and team readers need come
    from the frame record the journal writes next to the image.
    """
    for path in sorted(directory.glob('frame-*.json'), reverse=True):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if data.get('ocr') or data.get('size'):
            return data
    return None


def observe(tasker, directory, deadline):
    """Read the live page once and return its journal record.

    The analyze event itself carries no frame hash, tokens or size, so they are
    attached here: the repeated-card guard, the "did the click move the screen"
    check, the guide-book carousel and the pre-battle team reader all need them.
    """
    run_node(tasker, 'WindowMapObserve', deadline)
    record = events(directory, 'map_observed')[-1]
    if record['scene'] in ('BATTLE_HUD', 'BATTLE_PLANNING'):
        run_node(tasker, 'WindowBattleObserve', deadline)
        record = events(directory, 'battle_observed')[-1]
    if not record.get('image_sha256'):
        record['image_sha256'] = frame_sha(directory)
    details = frame_details(directory)
    if details:
        if not record.get('size'):
            record['size'] = details.get('size')
        if not record.get('ocr'):
            record['ocr'] = details.get('ocr')
    return record


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


def overlay_hit(registry, directory, record):
    """True when the guide book is on screen.

    Only identities that exist *without* the book count here: the book's carousel
    dots and the template of its own continue control. The page-turn triangle is
    deliberately not an identity -- it shares its right-hand band with other UI (the
    battle HUD's E.G.O resource column, the pre-battle page's warm Details button),
    and in live run window-20261006-034009 that turned twelve team page observations
    into "tutorial" clicks on the Details button.

    The glyph template is not an identity either: it only counts while a page-turn
    control is actually on screen. The battle HUD's E.G.O icon column scores inside
    the same ROI (0.706-0.858 across evidence/runtime/window-20261006-035540), and
    at 0.858 it crossed the 0.85 template threshold and refused a real battle page
    as ``tutorial_next_button_not_anchored``.
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
    report = anchors.evaluate(registry, observation, page='tutorial',
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
    return resolve_overlay(record['scene'],
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
    return {'states': card_states(records, boxes, size)}


def reward_state(record):
    """The encounter reward page's pick counter, as ``{'chosen': n, 'required': m}``.

    The page opens at ``Selectable 0/1`` and its Confirm button stays inert until a
    card is picked, so the driver hands the planner the counter rather than
    clicking blind (live: evidence/runtime/window-20261006-034714/frame-0022.json).
    The reading itself lives in :mod:`maalimbus.reward_vision` so it is unit tested
    offline, together with the merged-token case
    (evidence/runtime/window-20261006-035257/frame-0002.json).
    """
    return counter_state(record)


def gift_state(record, *, image=None, select_box=None, picks=0):
    """The floor gift page's pick state, as ``{'chosen': n, 'required': m, 'ready': b}``.

    The page ("Acquire E.G.O Gift") offers cards and confirms with one Select
    button that stays dark until the pick is satisfied. Two live variants exist: a
    four-card round printing ``Select 0/2`` (live:
    evidence/runtime/window-20261006-043102/frame-0003.json) and a three-card round
    printing a bare ``Select`` with no counter to read
    (evidence/runtime/window-20261006-043531). ``chosen`` therefore falls back to the
    driver's own count of the cards it has already clicked on this page, and
    ``ready`` comes from the button's pixels, which both variants share.
    """
    state = counter_state(record, band=GIFT_COUNTER_BAND) or {}
    chosen = state.get('chosen')
    return {'chosen': int(picks if chosen is None else chosen),
            'required': state.get('required'),
            'ready': select_ready(image, select_box) if select_box else None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, default=None)
    parser.add_argument('--input-method', default=None,
                        help='pin the ADB input method discovery offered (AdbShell, '
                             'MinitouchAndAdbKey, Maatouch, EmulatorExtras). Discovery '
                             'picks the highest-priority one Maa offers, and on this '
                             'MuMu both Maatouch and MinitouchAndAdbKey stopped '
                             'reaching the app while plain adb shell input tap kept '
                             'working, so the method may be pinned for a run')
    parser.add_argument('--address', required=True)
    parser.add_argument('--authorize', required=True)
    parser.add_argument('--steps', type=int, default=1,
                        help='how many planned inputs this window may send')
    parser.add_argument('--rounds', type=int, default=3,
                        help='read-only observations used to settle each step')
    parser.add_argument('--unknown-rounds', type=int, default=12,
                        help='how many consecutive UNKNOWN observations to wait through '
                             'before calling the page unreadable (loading screens, the turn '
                             'animation and the victory banner all read as UNKNOWN and are '
                             'not refusals; the victory banner alone held the screen for '
                             'about 25 s in window-20261006-033014)')
    parser.add_argument('--battle-rounds', type=int, default=8,
                        help='how many consecutive battle observations may report the same '
                             'wave and turn before the fight is called stalled; assigning and '
                             'submitting legitimately repeat for many turns, so the bound is '
                             'on the readouts moving, not on the clicks repeating')
    parser.add_argument('--interval', type=float, default=4.0)
    parser.add_argument('--map-tries', type=int, default=8,
                        help='how many map nodes one MAP step may try: a node that is not '
                             'connected to where the run stands opens no panel and is a '
                             'no-op, so the next candidate is tried instead of stopping '
                             '(a floor-1 frame shows up to six nodes, and only the ones '
                             'joined to the player by a path can open a panel)')
    parser.add_argument('--loop-guard', type=int, default=3,
                        help='stop after the same page/action/target plan passed this many '
                             'times in one run: a misleading overlay once produced twelve '
                             'passed rounds of TUTORIAL then To Battle! with nothing '
                             'changing. The guide book itself is exempt, because it '
                             'legitimately advances card by card from the same control')
    parser.add_argument('--observe-only', action='store_true',
                        help='record the page and send no input at all')
    parser.add_argument('--click-box', action='append', default=None,
                        help='x,y,w,h: send exactly one click and record the before/'
                             'after frames, for a control the anchors do not cover yet. '
                             'Repeat the option to send several clicks in one run')
    parser.add_argument('--label', default='one_shot_click',
                        help='what --click-box is aiming at, for the evidence record')
    parser.add_argument('--report', type=Path, default=None)
    args = parser.parse_args()
    if not authorized(args.authorize):
        print(json.dumps({'refused': 'live_input_not_authorized',
                          'hint': f'{AUTHORIZATION} must grant live_input_authorized '
                                  'with this nonce'}, ensure_ascii=False))
        return 2
    directory = ROOT / ('evidence/runtime/window-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 120 + args.steps * (args.rounds * (args.interval + 25)) \
        + (args.unknown_rounds + 1) * (args.interval + 20)
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    controls = controls_by_id(registry)
    result = dict(pid=os.getpid(), address=args.address, controller='Maa AdbController',
                  observe_only=bool(args.observe_only), steps=[], clicks_sent=0,
                  verified_clear=False, foreground_before=None)
    try:
        Library.open(args.binary, agent_server=False)
        Toolkit.init_option(prepare())
        device = discover(args.address, args.adb)
        allowed, reason = input_policy(device)
        if not allowed:
            result.update(refused=reason, passed=False)
            return 1
        device['input_policy'] = reason
        if args.input_method:
            device = pin_input(device, args.input_method)
            device['input_policy'] = reason + '+pinned_' + args.input_method
        controller = build(device, input_enabled=not args.observe_only)
        result.update(device=device, foreground_before=foreground_of(device))
        wait_job(controller.post_connection(), timeout=15, deadline=deadline)
        controller.set_screenshot_target_long_side(1920)
        journal = Journal(directory)
        recognition = LimbusRecognition('en', journal)
        resource = Resource()
        resource.register_custom_recognition('limbus_scene', recognition)
        resource.register_custom_action('limbus_map_observe', MapObservation(recognition))
        resource.register_custom_action('limbus_battle_observe', BattleObservation(recognition))
        for layer in ('base', 'en'):
            wait_job(resource.post_bundle(ROOT / f'assets/resource/{layer}'),
                     timeout=20, deadline=deadline)
        wait_job(resource.post_bundle(PIPELINE_DIR), timeout=20, deadline=deadline)
        tasker = Tasker()
        assert tasker.bind(resource=resource, controller=controller)

        page = None
        tutorial_cards = set()
        boxes = []
        for spec in (args.click_box or []):
            parts = [int(value) for value in spec.replace(' ', '').split(',')]
            if len(parts) != 4:
                raise ValueError('--click-box needs x,y,w,h')
            boxes.append(parts)
        for index, parts in enumerate(boxes):
            before = observe(tasker, directory, deadline)
            before_sha = before.get('image_sha256')
            inset = inset_box(tuple(parts), .3)
            point = (random.randint(inset[0], inset[0] + max(1, inset[2])),
                     random.randint(inset[1], inset[1] + max(1, inset[3])))
            delay = random.randint(350, 750)
            label = args.label if len(boxes) == 1 else f'{args.label}[{index}]'
            journal.record('one_shot_intent', label=label, box=parts,
                           point=list(point), delay_ms=delay)
            wait_job(controller.post_click(*point), timeout=10, deadline=deadline)
            result['clicks_sent'] += 1
            time.sleep(delay / 1000)
            after = before
            for round_index in range(max(1, args.rounds)):
                if round_index:
                    time.sleep(args.interval)
                after = observe(tasker, directory, deadline)
                if after.get('image_sha256') not in (None, before_sha):
                    break
            changed = after.get('image_sha256') not in (None, before_sha)
            result['steps'].append({
                'step': index, 'label': label, 'action': 'click', 'target': parts,
                'click_point': list(point), 'delay_ms': delay,
                'page_before': before['scene'], 'page_after': after['scene'],
                'scene_before': before['scene'], 'scene_after': after['scene'],
                'observation': before, 'settled': after, 'passed': bool(changed),
                'reason': ('one_shot_screen_changed' if changed
                           else 'one_shot_screen_unchanged')})
        goal = 0 if boxes else max(0, args.steps)
        step = 0
        unknown_seen = 0
        battle_sig = None
        battle_rounds = 0
        map_skips = set()
        map_attempts = 0
        gift_picks = 0
        repeated_plans = {}
        while step < goal:
            record = observe(tasker, directory, deadline)
            page = resolve_scene(registry, directory, record)
            frame, candidates = candidates_of(directory, record)
            choice_index = 0
            if page == 'EVENT_CHOICE':
                options = choice_options(record.get('ocr'), record.get('size'))
                candidates = [box for box, _text in options]
                choice_index = preferred_choice(options,
                                                gift_hints(record.get('ocr'),
                                                           record.get('size')))
            if page == 'MAP':
                candidates = [box for box in candidates if tuple(box) not in map_skips]
            sha = record.get('image_sha256')
            if not args.observe_only and page == 'UNKNOWN':
                unknown_seen += 1
                if unknown_seen > args.unknown_rounds:
                    result['steps'].append({
                        'step': step, 'page_before': page, 'scene_before': record['scene'],
                        'frame': frame, 'observation': record, 'plan': None,
                        'candidates': candidates, 'action': 'record',
                        'reason': 'page_unreadable_after_waiting', 'passed': False,
                        'clicks_sent': 0, 'stopped': 'page_unreadable_after_waiting'})
                    break
                # Loading screens and turn animations read as UNKNOWN; they are not a
                # refusal, so wait them out instead of stopping the window.
                journal.record('window_unknown_wait', round=unknown_seen,
                               interval_s=args.interval)
                time.sleep(args.interval)
                continue
            unknown_seen = 0
            if not args.observe_only and page == 'TUTORIAL' and sha in tutorial_cards:
                result['steps'].append({
                    'step': step, 'page_before': page, 'scene_before': record['scene'],
                    'frame': frame, 'observation': record, 'plan': None,
                    'candidates': candidates, 'action': 'record',
                    'reason': 'tutorial_card_repeated',
                    'passed': False, 'clicks_sent': 0,
                    'stopped': 'tutorial_card_repeated'})
                break
            if page == 'TUTORIAL' and sha:
                tutorial_cards.add(sha)
            if page in ('BATTLE_HUD', 'BATTLE_PLANNING'):
                # The battle is exempt from the repeated-plan guard because assigning
                # and submitting legitimate the same two controls for many turns, but
                # it is not exempt from progress: the wave and turn readouts have to
                # move. Ten-wave floor fights do run long, so the bound is generous.
                signature = (record.get('wave'), record.get('turn'))
                if signature == battle_sig:
                    battle_rounds += 1
                else:
                    battle_sig, battle_rounds = signature, 1
                if battle_rounds > args.battle_rounds:
                    result['steps'].append({
                        'step': step, 'page_before': page, 'scene_before': record['scene'],
                        'frame': frame, 'observation': record, 'plan': None,
                        'candidates': candidates, 'action': 'record',
                        'reason': 'battle_progress_stalled',
                        'passed': False, 'clicks_sent': 0,
                        'stopped': 'battle_progress_stalled'})
                    break
            team = team_state(record, controls) if page == 'PRE_BATTLE_TEAM' else None
            reward = reward_state(record) if page == 'REWARD_CARD' else None
            gift = None
            cards = None
            if page == 'GIFT_PICK':
                gift = gift_state(record, image=latest_frame(directory)[0],
                                  select_box=controls.get('gift_pick.select_button'),
                                  picks=gift_picks)
                cards = gift_cards(
                    [Text(t['text'], tuple(t['box']), t['score'])
                     for t in record.get('ocr') or []],
                    record.get('size') or (1920, 1080))
            else:
                gift_picks = 0
            plan = plan_step(page, controls=controls, arrows=arrows_of(directory),
                             start_box=record.get('start_box'),
                             auto_assign=record.get('auto_assign_buttons'),
                             candidates=candidates, candidate_index=choice_index,
                             team=team, reward=reward, gift=gift, cards=cards)
            entry = {'step': step, 'page_before': page, 'scene_before': record['scene'],
                     'frame': frame, 'observation': record, 'plan': plan, 'team': team,
                     'reward': reward, 'gift': gift, 'cards': cards,
                     'arrows': arrows_of(directory),
                     'candidates': candidates}
            if plan['action'] not in ('click', SWIPE, NODE) or args.observe_only:
                entry.update(step_result(plan, sent=False, before=page, after=None,
                                         page=page))
                entry['stopped'] = ('observe_only' if args.observe_only
                                    else plan['reason'])
                result['steps'].append(entry)
                if args.observe_only and step + 1 < goal:
                    step += 1
                    time.sleep(args.interval)
                    continue
                break
            point = None
            delay = random.randint(350, 750)
            if plan['action'] == NODE:
                journal.record('window_intent', page=page, node=plan['node'],
                               reason=plan['reason'], delay_ms=delay)
                run_node(tasker, plan['node'], deadline)
            elif plan['action'] == SWIPE:
                # A drag's start point is jittered inside its anchored box just like a
                # click, and its end point is jittered around the anchored pull target
                # (``to`` is a point, not a box); MuMu only ever sees Maa's simulated
                # touch, never the OS pointer.
                start = inset_box(tuple(plan['target']), .3)
                point = (random.randint(start[0], start[0] + max(1, start[2])),
                         random.randint(start[1], start[1] + max(1, start[3])))
                target_x, target_y = (int(value) for value in plan['to'])
                drop = (target_x + random.randint(-8, 8), target_y + random.randint(-8, 8))
                duration = int(plan.get('duration_ms') or 600)
                journal.record('window_intent', page=page, target=list(plan['target']),
                               reason=plan['reason'], point=list(point),
                               swipe_to=list(drop), duration_ms=duration, delay_ms=delay)
                wait_job(controller.post_swipe(point[0], point[1], drop[0], drop[1], duration),
                         timeout=10, deadline=deadline)
            else:
                box = inset_box(tuple(plan['target']), .3)
                x, y, w, h = box
                point = (random.randint(x, x + max(1, w)), random.randint(y, y + max(1, h)))
                journal.record('window_intent', page=page, target=list(plan['target']),
                               reason=plan['reason'], point=list(point), delay_ms=delay)
                wait_job(controller.post_click(*point), timeout=10, deadline=deadline)
            result['clicks_sent'] += 1
            entry.update(click_point=None if point is None else list(point), delay_ms=delay)
            time.sleep(delay / 1000)
            settled = None
            settled_page = None
            before_sha = record.get('image_sha256')
            for index in range(max(1, args.rounds)):
                if index:
                    time.sleep(args.interval)
                settled = observe(tasker, directory, deadline)
                settled_page = resolve_scene(registry, directory, settled)
                if settled_page not in (page, 'UNKNOWN'):
                    break
                # A tutorial card keeps the same page label but changes the pixels,
                # so a changed frame is the only evidence that the click landed.
                if settled.get('image_sha256') not in (None, before_sha):
                    break
            entry.update(page_after=settled_page, settled=settled,
                         scene_after=settled['scene'])
            entry.update(step_result(plan, sent=True, before=page,
                                     after=settled_page, page=settled_page,
                                     frame_changed=settled.get('image_sha256') not in (None, before_sha)))
            if not entry['passed'] and entry['reason'] == 'unexpected_successor':
                # Live run build/window-run36 pressed To Battle! on a full 12/12 team
                # page, and the settle loop still read PRE_BATTLE_TEAM while the game
                # had already moved into the battle: the successor arrives after the
                # transition, so one more observation decides whether the input was
                # swallowed or the frame was merely early. No second input is sent.
                time.sleep(args.interval)
                late = observe(tasker, directory, deadline)
                late_page = resolve_scene(registry, directory, late)
                if late_page != page:
                    entry.update(page_after=late_page, settled=late,
                                 scene_after=late['scene'], late_observation=True)
                    entry.update(step_result(plan, sent=True, before=page, after=late_page,
                                             page=late_page,
                                             frame_changed=late.get('image_sha256') not in (None, before_sha)))
            result['steps'].append(entry)
            if not entry['passed']:
                retryable = (page == 'MAP' and settled_page in ('MAP', 'UNKNOWN')
                             and plan.get('target') is not None
                             and map_attempts + 1 < max(1, args.map_tries))
                if not retryable:
                    entry['stopped'] = entry['reason']
                    break
                # An unreachable node swallows the click and the page stays MAP, so
                # skip it and let the next candidate be tried in its place.
                map_attempts += 1
                map_skips.add(tuple(plan['target']))
                entry['stopped'] = 'map_click_opened_no_panel'
                journal.record('window_map_retry', target=list(plan['target']),
                               attempt=map_attempts,
                               remaining=len([b for b in candidates
                                              if tuple(b) != tuple(plan['target'])]))
                continue
            map_attempts = 0
            if plan['reason'] == 'the_floor_gift_card_must_be_picked_before_select':
                gift_picks += 1
            if page not in LOOP_GUARD_EXEMPT:
                # A plan that keeps succeeding while the page never moves on is a
                # loop, not progress: live run window-20261006-034009 passed twelve
                # rounds of TUTORIAL then To Battle! with nothing changing underneath.
                # Battles are exempt because a fight legitimately alternates the same
                # two clicks (Win Rate then START) for as many turns as it has waves;
                # the step budget, not this guard, bounds them.
                key = (page, plan['action'], plan.get('node'),
                       None if plan.get('target') is None else tuple(plan['target']))
                repeated_plans[key] = repeated_plans.get(key, 0) + 1
                if repeated_plans[key] >= max(2, args.loop_guard):
                    entry['passed'] = False
                    entry['stopped'] = 'the_same_plan_repeated'
                    journal.record('window_loop_guard', plan=list(key),
                                   repeats=repeated_plans[key])
                    break
            step += 1
        result['foreground_after'] = foreground_of(device)
        last = result['steps'][-1] if result['steps'] else None
        result['page_before'] = None if last is None else last['page_before']
        result['page_after'] = None if last is None else last.get('page_after')
        result['passed'] = bool(result['steps']) and all(s['passed'] for s in result['steps'])
        result['reason'] = ('window_steps_passed' if result['passed']
                            else ((last or {}).get('stopped') or (last or {}).get('reason')
                                  or 'no_step_recorded'))
    except Exception as error:
        result.update(reason='window_failed', error=str(error), passed=False)
        raise
    finally:
        report = directory / 'result.json'
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                          encoding='utf-8')
        if args.report:
            Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                         encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items()
                          if k not in ('steps', 'device', 'foreground_before',
                                       'foreground_after')},
                         ensure_ascii=False, indent=1))
        for entry in result['steps']:
            print(json.dumps({'step': entry['step'], 'page_before': entry['page_before'],
                              'page_after': entry.get('page_after'),
                              'action': entry.get('action'), 'reason': entry.get('reason'),
                              'passed': entry.get('passed'),
                              'arrows': entry.get('arrows'),
                              'stopped': entry.get('stopped')}, ensure_ascii=False))
        lease.close()
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
