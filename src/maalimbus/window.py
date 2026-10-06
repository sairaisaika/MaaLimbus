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

#: pages that end the walk: a fresh observation is taken and the window stops.
OBSERVE_ONLY = ('SHOP', 'EVENT_DIALOG', 'REWARD_SETTLE', 'FLOOR_GIFTS',
                'BATTLE_RESULT', 'UNKNOWN')

#: pages whose only input is an existing, already proven pipeline node.
PAGE_NODES = {'DRIVE': 'WindowDrive'}

#: controls a window must never click, whatever else is on the same page. Halt
#: Exploration throws an in-progress run away, so it stays registered as an
#: anchor (its label is how the page is identified) but is refused as a target.
FORBIDDEN_CONTROLS = ('resume.halt_button',)


def resolve_overlay(page, *, overlay_hit):
    """Return the page the tutorial overlay covers, while its control is visible.

    Live proof: ``evidence/runtime/window-20261006-024050/frame-0002.json`` is the
    overlay's second card ("Weekly Bonuses"). The OCR token only knew the first
    card, so the covered entry page was planned and its inert ``Enter`` swallowed
    the step. The overlay's own continue control does not change from card to
    card, so a visible continue control outranks the label underneath it.
    """
    return 'TUTORIAL' if overlay_hit else page


def _plan(page, action, *, target=None, node=None, expect=(), reason, detail=None):
    plan = {'page': page, 'action': action,
            'target': None if target is None else list(target),
            'node': node, 'expect': list(expect), 'reason': reason}
    if detail is not None:
        plan['detail'] = detail
    return plan


def _refuse(page, reason):
    return _plan(page, RECORD, reason=reason)


def plan_step(page, *, controls=None, start_box=None, auto_assign=None,
              candidates=None, candidate_index=0, nodes=None):
    """Return the one input (or the refusal) allowed on ``page``.

    A plan that would land on a control in :data:`FORBIDDEN_CONTROLS` is refused
    here, so a mis-registered anchor can never abandon a run by itself.
    """
    controls = controls or {}
    plan = _plan_step(page, controls=controls, start_box=start_box,
                      auto_assign=auto_assign, candidates=candidates,
                      candidate_index=candidate_index, nodes=nodes)
    forbidden = {tuple(box) for name, box in controls.items()
                 if name in FORBIDDEN_CONTROLS}
    if plan.get('target') and tuple(plan['target']) in forbidden:
        return _refuse(page, 'control_is_forbidden')
    return plan


def _plan_step(page, *, controls=None, start_box=None, auto_assign=None,
               candidates=None, candidate_index=0, nodes=None):
    """Return the one input (or the refusal) allowed on ``page``.

    ``controls`` maps anchor names such as ``node_panel.enter_button`` to pixel
    boxes; ``start_box`` and ``auto_assign`` come from the battle observation;
    ``candidates`` are node boxes read from the live map frame; ``nodes`` maps a
    page to an existing pipeline node that already carries its own proven
    recognition and click box.
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
        box = controls.get('tutorial.next_button')
        if box is None:
            return _refuse(page, 'tutorial_next_button_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('TUTORIAL', 'MIRROR_ENTRY', 'THEME_PACKS', 'MAP', 'UNKNOWN'),
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
        box = controls.get('pre_battle.battle_button')
        if box is None:
            return _refuse(page, 'battle_button_not_anchored')
        return _plan(page, CLICK, target=box, expect=('BATTLE_HUD', 'THEME_PACKS', 'UNKNOWN'),
                     reason='battle_button_submits_the_team')
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
    """True when the successor page is inside the plan's expected set.

    An empty expectation set means the plan sent no input, so any page is fine.
    """
    if plan.get('action') not in (CLICK, NODE):
        return True
    expect = plan.get('expect') or []
    return page in expect


def step_result(plan, *, sent, before, after, page):
    """Assemble the recorded step verdict for one planned input."""
    if not sent:
        return {'action': plan['action'], 'reason': plan['reason'], 'passed': False,
                'page_before': before, 'page_after': after or before,
                'clicks_sent': 0}
    ok = successor_ok(plan, page)
    return {'action': plan['action'], 'reason': plan['reason'] if ok else 'unexpected_successor',
            'passed': ok, 'page_before': before, 'page_after': page,
            'expect': list(plan.get('expect') or []), 'clicks_sent': 1}
