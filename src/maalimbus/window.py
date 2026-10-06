"""Page-to-action planning for a bounded live verification window.

A window is one continuous live session that walks the dungeon loop and records
every page it meets, so that pages which can only be confirmed by looking at the
screen are confirmed once, in one batch, and afterwards the script works from
recorded numbers and anchors only.

The driver (``tools/window_step.py``) reads one fresh page, asks this module for
the single input it may send next, sends it, and then compares the successor page
against the expected set. The table lives here so it can be unit tested without a
device, and so the same reasoning can be lifted into agent pipeline actions later.

Rules encoded here:

* a page never sends more than one input per plan;
* a page with no proven control refuses instead of guessing a coordinate;
* a click is only accepted when the successor page is one of the expected pages,
  otherwise the step is recorded as ``unexpected_successor`` and the window stops;
* battle turns are submitted only when the game itself shows ``START``.
"""

from __future__ import annotations

CLICK = 'click'
NODE = 'node'
RECORD = 'record'

#: expectation sentinel for a dismissal: the successor is proven by the covered
#: page being gone, not by which page it uncovered. The overlay's cards walk
#: through many different pages, so no positive list can name them all, but
#: "still the overlay" is a decidable failure.
ANY = '*'

#: pages that end the walk: a fresh observation is taken and the window stops.
OBSERVE_ONLY = ('SHOP', 'EVENT_DIALOG', 'REWARD_SETTLE', 'FLOOR_GIFTS',
                'BATTLE_RESULT', 'UNKNOWN')

#: pages whose only input is an existing, already proven pipeline node.
PAGE_NODES = {'DRIVE': 'WindowDrive'}

#: controls a window must never click, whatever else is on the same page. Halt
#: Exploration throws an in-progress run away, and Cancel on the encounter reward
#: page refuses a reward the run has already earned, so both stay registered as
#: anchors (their labels are how the page is identified) but are refused as targets.
FORBIDDEN_CONTROLS = ('resume.halt_button', 'reward_card.cancel_button')


def resolve_overlay(page, *, overlay_hit):
    """Return the page the tutorial overlay covers, while its control is visible.

    Live proof: ``evidence/runtime/window-20261006-024050/frame-0002.json`` is the
    overlay's second card ("Weekly Bonuses"). The OCR token only knew the first
    card, so the covered entry page was planned and its inert ``Enter`` swallowed
    the step. The overlay's own continue control does not change from card to
    card, so a visible continue control outranks the label underneath it.
    """
    return 'TUTORIAL' if overlay_hit else page


def _plan(page, action, *, target=None, node=None, expect=(), reason, detail=None,
          advance=False):
    plan = {'page': page, 'action': action,
            'target': None if target is None else list(target),
            'node': node, 'expect': list(expect), 'reason': reason,
            'advance': bool(advance)}
    if detail is not None:
        plan['detail'] = detail
    return plan


def _refuse(page, reason):
    return _plan(page, RECORD, reason=reason)


def plan_step(page, *, controls=None, start_box=None, auto_assign=None,
              candidates=None, candidate_index=0, nodes=None, arrows=None, team=None,
              reward=None):
    """Return the one input (or the refusal) allowed on ``page``.

    A plan that would land on a control in :data:`FORBIDDEN_CONTROLS` is refused
    here, so a mis-registered anchor can never abandon a run by itself.
    """
    controls = controls or {}
    plan = _plan_step(page, controls=controls, start_box=start_box,
                      auto_assign=auto_assign, candidates=candidates,
                      candidate_index=candidate_index, nodes=nodes, arrows=arrows,
                      team=team, reward=reward)
    forbidden = {tuple(box) for name, box in controls.items()
                 if name in FORBIDDEN_CONTROLS}
    if plan.get('target') and tuple(plan['target']) in forbidden:
        return _refuse(page, 'control_is_forbidden')
    return plan


def _plan_step(page, *, controls=None, start_box=None, auto_assign=None,
               candidates=None, candidate_index=0, nodes=None, arrows=None, team=None,
               reward=None):
    """Return the one input (or the refusal) allowed on ``page``.

    ``controls`` maps anchor names such as ``node_panel.enter_button`` to pixel
    boxes; ``start_box`` and ``auto_assign`` come from the battle observation;
    ``candidates`` are node boxes read from the live map frame; ``nodes`` maps a
    page to an existing pipeline node that already carries its own proven
    recognition and click box; ``team`` carries the pre-battle page's per-card
    participation badges; ``reward`` carries the encounter reward page's pick
    counter (``{'chosen': n, 'required': m}``).
    """
    controls = controls or {}
    nodes = dict(PAGE_NODES, **(nodes or {}))
    if page == 'HOME':
        box = controls.get('home.drive_button')
        if box is None:
            return _refuse(page, 'drive_button_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('DRIVE', 'MIRROR_ENTRY', 'THEME_PACKS', 'MAP', 'UNKNOWN'),
                     reason='drive_nav_is_the_proven_way_back_to_the_mirror_menu')
    if page == 'DRIVE':
        node = nodes.get('DRIVE')
        if node is None:
            return _refuse(page, 'mirror_menu_node_not_registered')
        return _plan(page, NODE, node=node,
                     expect=('MIRROR_ENTRY', 'DRIVE', 'THEME_PACKS', 'MAP', 'UNKNOWN'),
                     reason='mirror_menu_recognition_owns_the_click_box')
    if page == 'TUTORIAL':
        # ``arrows`` comes from the live frame (maalimbus.overlay_vision): the two
        # page-turn triangles move, and the book's last page shows only ``previous``
        # (live: evidence/runtime/window-20261006-030152/frame-0014.png), where a
        # fixed right-edge box clicks empty space and proves nothing.
        arrows = arrows or {}
        if arrows.get('next'):
            box = arrows['next']
        elif arrows:
            box = None
        else:
            box = controls.get('tutorial.next_button')
        if box is None:
            if arrows.get('previous'):
                # Last card of the book: there is no forward page-turn control, and
                # the only way out is the book's own header arrow, which closes it
                # and uncovers the page underneath (live: clicking it over the team
                # page reached PRE_BATTLE_TEAM).
                close = controls.get('tutorial.book_close')
                if close is None:
                    return _refuse(page, 'tutorial_last_page_has_no_forward_control')
                return _plan(page, CLICK, target=close, expect=(ANY,), advance=True,
                             reason='tutorial_last_page_is_closed_from_the_book_header')
            return _refuse(page, 'tutorial_next_button_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='tutorial_overlay_must_be_dismissed_before_enter_is_live')
    if page == 'MIRROR_ENTRY':
        box = controls.get('entry.enter_button')
        if box is None:
            return _refuse(page, 'entry_enter_button_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('STAR_GRACES', 'INITIAL_GIFTS', 'THEME_PACKS', 'MAP',
                             'LEVEL_WARNING', 'ENTRY_CONFIRM', 'UNKNOWN'),
                     reason='before_entry_enter_starts_the_free_run')
    if page == 'RESUME_DIALOG':
        box = controls.get('resume.resume_button')
        if box is None:
            return _refuse(page, 'resume_button_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('MAP', 'THEME_PACKS', 'STAR_GRACES', 'INITIAL_GIFTS', 'UNKNOWN'),
                     reason='resume_rejoins_the_run_that_is_already_in_progress')
    if page == 'MAP':
        if not candidates:
            return _refuse(page, 'no_candidate_node_observed')
        if not 0 <= candidate_index < len(candidates):
            return _refuse(page, 'candidate_index_out_of_range')
        return _plan(page, CLICK, target=candidates[candidate_index],
                     expect=('NODE_PANEL',),
                     reason='map_node_click_is_the_only_proven_forward_input',
                     detail={'candidate_count': len(candidates),
                             'candidate_index': candidate_index})
    if page == 'NODE_PANEL':
        box = controls.get('node_panel.enter_button')
        if box is None:
            return _refuse(page, 'enter_button_not_anchored')
        return _plan(page, CLICK, target=box, expect=('PRE_BATTLE_TEAM', 'UNKNOWN'),
                     reason='panel_enter_is_the_only_forward_input')
    if page == 'PRE_BATTLE_TEAM':
        # The page opens with nobody picked, and its Battle! button is dark until
        # at least one card is in the team (live: window-20261006-030750 has
        # 0/12 and a dim button; window-20261006-030941 has 12/12 and a bright
        # one). Selecting is per card and never touches the identity, so the only
        # safe move is to pick the first card that still has no badge.
        states = list((team or {}).get('states') or [])
        for index, state in enumerate(states):
            box = controls.get('pre_battle.card_%02d' % (index + 1))
            if state is None and box is not None:
                return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                             reason='team_card_joins_the_next_unpicked_identity',
                             detail={'card_index': index + 1})
        box = controls.get('pre_battle.battle_button')
        if box is None:
            return _refuse(page, 'battle_button_not_anchored')
        return _plan(page, CLICK, target=box, expect=('BATTLE_HUD', 'THEME_PACKS', 'UNKNOWN'),
                     reason='battle_button_submits_the_team')
    if page == 'REWARD_CARD':
        # A cleared node hands back a pick-one reward screen ("Selectable 0/1").
        # Confirm does nothing until a card is picked, so the planner reads the
        # counter instead of clicking blind. Cancel is a registered anchor (its
        # label is part of the page identity) and is refused as a target, because
        # refusing a reward the run already earned is a forbidden input.
        state = reward or {}
        chosen = int(state.get('chosen') or 0)
        required = int(state.get('required') or 1)
        if chosen < required:
            box = controls.get('reward_card.card_01')
            if box is None:
                return _refuse(page, 'reward_card_box_not_anchored')
            return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                         reason='the_reward_card_must_be_picked_before_confirm',
                         detail={'chosen': chosen, 'required': required})
        box = controls.get('reward_card.confirm_button')
        if box is None:
            return _refuse(page, 'reward_card_confirm_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='confirm_grants_the_picked_encounter_reward')
    if page == 'BATTLE_HUD':
        if start_box:
            return _plan(page, CLICK, target=start_box,
                         expect=('BATTLE_HUD', 'BATTLE_RESULT', 'UNKNOWN'),
                         reason='start_button_submits_the_assigned_turn')
        if auto_assign and auto_assign.get('win_rate'):
            return _plan(page, CLICK, target=auto_assign['win_rate'],
                         expect=('BATTLE_HUD', 'BATTLE_RESULT', 'UNKNOWN'),
                         reason='win_rate_is_the_proven_auto_assign_control')
        return _refuse(page, 'battle_has_no_proven_control')
    return _refuse(page, 'page_is_observe_only')


def successor_ok(plan, page):
    """True when the successor page satisfies the plan's expectation.

    An empty expectation set means the plan sent no input, so any page is fine.
    :data:`ANY` is the dismissal case: the click is proven by the covered page
    being gone, so every successor except the plan's own page passes.
    """
    if plan.get('action') not in (CLICK, NODE):
        return True
    if page == 'TUTORIAL' and plan.get('page') != 'TUTORIAL':
        # The guide book pops up over any page without warning (live: it covered
        # the battle HUD right after "To Battle!"), so its appearance never
        # disproves the input that preceded it; the next step dismisses it.
        return True
    expect = plan.get('expect') or []
    if ANY in expect:
        return page != plan.get('page')
    return page in expect


def step_result(plan, *, sent, before, after, page, frame_changed=False):
    """Assemble the recorded step verdict for one planned input.

    ``frame_changed`` is the pixel evidence that the screen moved on. An
    ``advance`` plan is one whose own page is expected to stay: the tutorial
    overlay walks card after card, so a changed frame is the proof that the click
    landed even while the page label is unchanged.
    """
    if not sent:
        return {'action': plan['action'], 'reason': plan['reason'], 'passed': False,
                'page_before': before, 'page_after': after or before,
                'clicks_sent': 0}
    ok = successor_ok(plan, page) or (plan.get('advance') and frame_changed)
    return {'action': plan['action'], 'reason': plan['reason'] if ok else 'unexpected_successor',
            'passed': ok, 'page_before': before, 'page_after': page,
            'expect': list(plan.get('expect') or []), 'clicks_sent': 1}
