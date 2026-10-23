"""One registry for every page name the dungeon loop can meet.

Audit finding (2026-10-23): page names are produced by **two** modules --
``src/maalimbus/vision.py`` (:func:`classify`) and ``agent/recognition.py``
(scene literals) -- and handled by **two** more -- ``window.plan_step``'s 52
branches and inline code in ``runner.py``.  Nothing checked that those four
agree, so a new page could be classified and never planned, or planned under a
name the classifier never returns, and the only symptom was a stop.

This module is the index, not a second dispatcher: it records, for each page,
who produces it and which layer owns the decision.  ``tests/test_pages.py``
fails when a name appears in a producer without a row here, so "where is this
page handled?" is a one-line lookup instead of three greps.

``handling`` values:

* ``plan``     -- ``window.plan_step`` has a branch for it;
* ``wait``     -- it clears itself (``window.WAIT_PAGES``);
* ``observe``  -- a fresh observation is taken and the window stops
                  (``window.OBSERVE_ONLY``);
* ``runner``   -- ``runner.py`` decides inline (battle HUD, planning, entry,
                  resource dialog, team library).  Countable on purpose: these
                  are the pages the window table does not own.
"""

from __future__ import annotations

import ast
from collections import Counter

PAGES = {
    'BATTLE_DEFEAT': ('vision', 'plan'),
    'BATTLE_HUD': ('vision+agent', 'runner'),
    'BATTLE_PLANNING': ('agent', 'runner'),
    'BATTLE_RESULT': ('vision', 'wait'),
    'BATTLE_TIP': ('vision', 'plan'),
    'BATTLE_VICTORY': ('vision', 'plan'),
    'CUTSCENE': ('vision', 'plan'),
    'DEFEAT': ('vision', 'wait'),
    'DEPLOYMENT': ('agent', 'plan'),
    'DEPLOYMENT_RESET': ('vision', 'plan'),
    'DRIVE': ('vision', 'plan'),
    'DUNGEON_PROGRESS': ('vision', 'plan'),
    'DUNGEON_TEAM': ('vision', 'plan'),
    'EGO_GIFT_POPUP': ('vision', 'plan'),
    'ENTRY_CONFIRM': ('vision', 'plan'),
    'EVENT_CHECK': ('vision', 'plan'),
    'EVENT_CHECK_READY': ('vision', 'plan'),
    'EVENT_CHECK_RESULT': ('vision', 'plan'),
    'EVENT_CHOICE': ('vision', 'plan'),
    'EVENT_DIALOG': ('unknown', 'observe'),
    'EVENT_RESULT': ('vision', 'plan'),
    'EVENT_RESULT_READY': ('vision', 'plan'),
    'EXPIRED_SESSION': ('vision', 'plan'),
    'EXPLORATION_COMPLETE': ('vision', 'plan'),
    'FLOOR_GIFTS': ('vision', 'observe'),
    'GIFT_GET': ('vision+agent', 'plan'),
    'GIFT_PICK': ('vision+agent', 'plan'),
    'GIFT_SEARCH': ('vision+agent', 'plan'),
    'GIFT_SEARCH_FORGO': ('vision', 'plan'),
    'GIFT_WARNING': ('vision', 'plan'),
    'HEAL_SINNERS': ('vision', 'plan'),
    'HOME': ('vision', 'plan'),
    'INITIAL_GIFTS': ('agent', 'plan'),
    'LEVEL_WARNING': ('vision', 'plan'),
    'MAP': ('agent', 'plan'),
    'MIRROR_ENTRY': ('vision', 'runner'),
    'NODE_PANEL': ('agent', 'plan'),
    'PASS_LEVEL_UP': ('vision', 'plan'),
    'PRE_BATTLE_TEAM': ('agent', 'plan'),
    'RESOURCE_DIALOG': ('vision', 'runner'),
    'RESUME_DIALOG': ('vision', 'plan'),
    'REVIVE_DONE': ('vision', 'plan'),
    'REVIVE_PICK': ('vision', 'plan'),
    'REWARD_CARD': ('vision', 'plan'),
    'REWARD_SETTLE': ('unknown', 'observe'),
    'RUN_CLAIM': ('vision', 'plan'),
    'RUN_REWARD_BONUS': ('vision', 'plan'),
    'RUN_REWARD_CONFIRM': ('vision', 'plan'),
    'RUN_REWARD_DIALOG': ('vision', 'plan'),
    'SHOP': ('vision+agent', 'observe'),
    'SHOP_LEAVE': ('vision', 'plan'),
    'SHOP_PURCHASE': ('vision+agent', 'plan'),
    'STAR_CONFIRM': ('vision+agent', 'plan'),
    'STAR_GRACES': ('agent', 'plan'),
    'TEAM_LIBRARY': ('vision', 'runner'),
    'THEME_PACKS': ('agent', 'plan'),
    'TUTORIAL': ('vision', 'plan'),
    'UNKNOWN': ('vision+agent', 'wait'),
    'UNKNOWN_DIALOG': ('vision', 'plan'),
    'WINDOW_RESET': ('vision', 'plan'),
}


#: Pages `window.OBSERVE_ONLY` names but that no producer ever emits
#: (measured 2026-10-23: neither `vision.classify` nor `agent/recognition.py`
#: contains the literal).  They are dead entries in that list, not a missing
#: producer, and are recorded here so the next reader does not hunt for one.
UNREACHABLE = ('EVENT_DIALOG', 'REWARD_SETTLE')


#: Per-page contract: the four questions every state must answer before the loop
#: may act on it.  Only the pages that historically dead-locked are written down
#: so far; `tests/test_pages.py` requires each entry to name real pages.
CONTRACTS = {
    'MAP': {
        'entry_evidence': ('Exploring Floor <n> header readable OR the page '
                           'classifier returned MAP from the agent scene'),
        'allowed_inputs': ('click a candidate node that is adjacent to the party',
                           'open the gear to the progress panel',
                           'leave the floor when the summary is offered'),
        'success_proof': ('the party moved one lattice pitch, OR the successor '
                          'page is not MAP, OR a verdict fired'),
        'failure_handling': ('bounded re-read, then the viewport ladder '
                             '(pinch out / pan), then a typed stop'),
        'irreversible': (),
    },
    'SHOP': {
        'entry_evidence': ('"Shop" title with a Leave control and an offer grid'),
        'allowed_inputs': ('buy when the receipt is proven', 'leave the shop'),
        'success_proof': ('the purchase dialog answered and the balance moved, '
                          'OR the successor page is not SHOP'),
        'failure_handling': ('cancel an unproven purchase and leave; never '
                             're-send an unclosed transaction'),
        'irreversible': ('a confirmed purchase',),
    },
    'DUNGEON_PROGRESS': {
        'entry_evidence': ('"Dungeon Progress" panel with Resume / Halt / Cancel'),
        'allowed_inputs': ('continue (closes the panel)', 'resume the exploration',
                           'halt the exploration'),
        'success_proof': 'the panel is gone',
        'failure_handling': ('re-read once, then stop with the missing control '
                             'named by the anchor contract'),
        'irreversible': ('halting an exploration throws the run away',),
    },
}


#: The spellings of "which page is this" the loop actually uses.  The first
#: ratchet (D35, 2026-10-23) counted only ``page == 'X'`` and therefore saw 85
#: of the 125 dispatch sites in ``runner.py``: ``page != 'X'``,
#: ``page in (...)``, ``settled_page in (...)`` and ``page in CONSTANTS`` were
#: invisible, which is how a page could gain a sixth check without the guard
#: noticing.
DISPATCH_READERS = ('page', 'settled_page', 'was_page')

#: A comparator that names no page statically (``page in WAIT_PAGES``) is
#: counted under this name, so growth in that form is still growth.
UNRESOLVED_PAGE = '?'


def _read_page(node):
    """The spelling of "which page is this" in ``node``, or ``None``."""
    if isinstance(node, ast.Name) and node.id in DISPATCH_READERS:
        return node.id
    if isinstance(node, ast.Attribute) and node.attr == 'page':
        return 'attribute'
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'get' and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == 'page'):
        return 'get'
    if (isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == 'page'):
        return 'subscript'
    return None


def _page_names(target):
    """The page names a comparator names, or ``[UNRESOLVED_PAGE]``."""
    if isinstance(target, ast.Constant) and isinstance(target.value, str):
        return [target.value]
    if isinstance(target, (ast.Tuple, ast.List, ast.Set)):
        names = [element.value for element in target.elts
                 if isinstance(element, ast.Constant)
                 and isinstance(element.value, str)]
    elif isinstance(target, ast.Dict):
        names = [key.value for key in target.keys
                 if isinstance(key, ast.Constant) and isinstance(key.value, str)]
    else:
        names = []
    return names or [UNRESOLVED_PAGE]


def dispatch_sites(source):
    """Every inline page-dispatch site in ``source``, counted per page name.

    A site is one comparison of a page reader against page names, in any of the
    forms the loop writes: ``==``, ``!=``, ``in``, ``not in``, on either side,
    through a name, an attribute, ``.get('page')`` or ``['page']``.  Membership
    of several names counts once for each name it tests, so a site that handles
    three pages costs three rows -- but one *site*, and that is what the
    ratchets below bound.

    Counting the population rather than one spelling is the whole point: the
    first version of this ratchet (D35) matched ``page == 'X'`` with a regex and
    reported 85 of 125.
    """
    counts = Counter()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if not isinstance(node.ops[0], (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
            continue
        left, right = node.left, node.comparators[0]
        if _read_page(left) is not None:
            target = right
        elif _read_page(right) is not None:
            target = left
        else:
            continue
        for name in _page_names(target):
            counts[name] += 1
    return counts


#: Inline page dispatch in ``runner.py``, re-measured 2026-10-23 with
#: :func:`dispatch_sites`: **149 rows across 125 sites and 34 names**, of which
#: ``MAP`` alone is 29.  The first table counted only ``page == 'X'`` and so
#: recorded 85 rows across 23 names: ``page != 'X'`` (9), ``page in (...)`` (11),
#: ``settled_page in (...)`` (8), ``page in CONST`` (7) and
#: ``state.get('page')`` were invisible, i.e. the ratchet guarded two thirds of
#: the surface it claimed to guard.
#:
#: This is a **ratchet, not a target**: the numbers may go down as cases move
#: into ``window``/``pages``, and ``tests/test_pages.py`` fails if any of them
#: goes up.  A new page-specific inline check must therefore either replace an
#: existing one or be argued for by editing this table deliberately.
INLINE_RUNNER = {
    '?': 13,
    'BATTLE_DEFEAT': 1,
    'BATTLE_HUD': 4,
    'BATTLE_PLANNING': 1,
    'DEPLOYMENT': 4,
    'DEPLOYMENT_RESET': 3,
    'DUNGEON_PROGRESS': 1,
    'DUNGEON_TEAM': 6,
    'EVENT_CHOICE': 1,
    'EVENT_RESULT': 2,
    'GIFT_GET': 12,
    'GIFT_PICK': 5,
    'GIFT_SEARCH': 1,
    'HEAL_SINNERS': 2,
    'INITIAL_GIFTS': 4,
    'MAP': 29,
    'PRE_BATTLE': 1,
    'PRE_BATTLE_TEAM': 6,
    'RESUME_DIALOG': 1,
    'REVIVE_DONE': 2,
    'REVIVE_PICK': 1,
    'REWARD_CARD': 3,
    'RUN_REWARD_BONUS': 1,
    'RUN_REWARD_CONFIRM': 1,
    'RUN_REWARD_DIALOG': 1,
    'SHOP': 7,
    'SHOP_PURCHASE': 5,
    'STAR_CONFIRM': 3,
    'STAR_GRACES': 9,
    'TEAM_LIBRARY': 1,
    'THEME_PACKS': 3,
    'TUTORIAL': 3,
    'UNKNOWN': 8,
    'UNKNOWN_DIALOG': 4,
}

#: The same count for ``window.py``: **61 rows across 58 sites**, the chain
#: ``window.plan_step`` walks before the runner sees a page.  It is ratcheted
#: too, because a page moved out of the runner's chain and into this one is the
#: same page-by-page growth one module later -- the move is allowed, it just has
#: to show up in a diff instead of in a stop.
INLINE_WINDOW = 61



def inline_overrun(counts):
    """Pages whose inline checks grew past the recorded baseline."""
    return sorted(name for name, n in counts.items()
                  if n > INLINE_RUNNER.get(name, 0))


def window_overrun(counts):
    """How many rows of ``window.py`` dispatch the baseline no longer covers."""
    return max(0, sum(counts.values()) - INLINE_WINDOW)


def producers(name):
    """Which module(s) can emit ``name`` (``'vision'``, ``'agent'`` or both)."""
    row = PAGES.get(name)
    return None if row is None else row[0].split('+')


def handling(name):
    """Who decides the next input on ``name``, or None when unregistered."""
    row = PAGES.get(name)
    return None if row is None else row[1]


def by_handling(kind):
    return sorted(name for name, (_, kind_) in PAGES.items() if kind_ == kind)


def undeclared(names):
    """Names a producer emits that this registry does not know (guard test)."""
    return sorted({n for n in names if n not in PAGES})

#: The closed vocabulary of refusal reasons.  ``window._refuse`` may only use a
#: reason from this map; ``tests/test_refuse_vocabulary.py`` enforces it.  The value
#: is the *state* the refusal describes, so a new page reuses an existing state
#: instead of coining a string:  missing_control / unread_page / refused_by_policy.
# What a refusal *means*, independent of the string that names it.  A page-specific
# reason (`tutorial_last_page_has_no_forward_control`) tells a human where to look; the
# class tells the engine what it may do next -- bind a control, try another candidate,
# give up, re-read the text, or distrust our own saved state.  Six classes, no more:
# a seventh would mean the recovery engine grew a new decision it does not have.
REFUSAL_KINDS = ('missing_control', 'no_candidate', 'attempts_exhausted',
                 'unreadable_text', 'bad_saved_state', 'refused_by_policy')

# What the engine may do next, given the kind.  One action per kind, so the decision
# is a table rather than a branch: a new page-specific refusal inherits its kind's
# action automatically, and the six kinds can never disagree with each other.
RECOVERY_BY_KIND = {
    'missing_control': 'bind_control',
    'no_candidate': 'pan_view',
    'attempts_exhausted': 'escalate_ladder',
    'unreadable_text': 'reread_text',
    # `recompute_state` used to hold this kind.  Re-measured on the whole retained
    # archive with `tools/recovery_outcome.py` (939 runs, 2026-10-23), which now counts
    # "no input ever followed" as no evidence instead of as a change: the page changed
    # after rewiring state in 19 of 40 evidenced spends (48%), and after escalating the
    # ladder in 7 of 14 (50%) -- the earlier "0 of 51" does not reproduce and is
    # retired.  The two are indistinguishable by outcome, so the tie is broken by the
    # one difference that matters for a screen that disagrees with our saved state:
    # a wait-only action cannot change it, and escalate is the bounded action that can.
    'bad_saved_state': 'escalate_ladder',
    'refused_by_policy': 'stop',
}

# Every action the table is allowed to name.  `recompute_state` is deliberately absent:
# no kind produces it any more (see `SUPERSEDED_ACTIONS`), and a guard that let it back
# in silently would undo the measurement above without anyone noticing.
RECOVERY_ACTIONS = ('bind_control', 'pan_view', 'escalate_ladder', 'reread_text', 'stop')

# Kinds that deliberately share an action.  Sharing is a decision, not an accident:
# `attempts_exhausted` and `bad_saved_state` both climb the same ladder because the
# ladder is the only bounded action that changes a screen, and each kind still records
# which of the two decided (`deciding_kind`).  A *new* shared action is a new decision.
SHARED_ACTIONS = {'escalate_ladder': ('attempts_exhausted', 'bad_saved_state')}

# Actions a retained event may still carry from the build that wrote it, after the
# policy moved on.  Measured in `evidence/runtime/packaged-mirror-*`: `bad_saved_state`
# recorded `reset_state` 3 times, `recompute_state` 60 times, and `escalate_ladder` 21
# times, in that order -- each was the policy of its own build.  Evidence is judged by
# the build that wrote it; anything outside this list is a real contradiction, which is
# what `evidence_audit.inconsistent_decisions` checks.
SUPERSEDED_ACTIONS = {'bad_saved_state': ('reset_state', 'recompute_state')}




# Which rungs a refusal's action may use.  Narrowing is the *only* safe direction:
# an unknown action falls back to the measured six-rung ladder, because a gesture that
# moves a view has never corrupted a run, while dragging a text screen can misroute it.
WAIT_ONLY_ACTIONS = ('bind_control', 'reread_text', 'recompute_state')


def ladder_for(action, ladder):
    """The rungs this action may spend, in order.  Never invents a rung."""
    if action == 'stop':
        return ()
    if action in WAIT_ONLY_ACTIONS:
        return tuple(rung for rung in ladder if rung[0] == 'wait')
    return tuple(ladder)


def superseded_click(pending, target):
    """Was a planned map click replaced before its page settled?

    The live run of 2026-10-22 planned three node clicks inside one page settle and
    recorded one verdict, because the pending target was overwritten without being
    judged.  An unjudged click also cannot reach `map_refused_streak`, which is what
    decides that a suspended exploration was never resumed -- so the click has to be
    *named* as replaced, not dropped.
    """
    if not pending:
        return False
    return list(pending) != list(target)


def recovery_for(kind):
    """The action for a refusal kind; an unknown kind holds instead of guessing."""
    return RECOVERY_BY_KIND.get(kind, 'hold')


# The runner stops a run with its own vocabulary (`stopped_reason`), which is *not* the
# refusal vocabulary `window._refuse` writes: measured on
# `evidence/runtime/packaged-mirror-20261023-084610`, two recoveries carried
# `page_unreadable_after_waiting` and `unexpected_successor` and neither existed in
# `REFUSALS`, so the kind stayed null and the audit could never see them.  One table
# per vocabulary, joined here, instead of quietly growing either one.
STOP_KINDS = {
    'page_unreadable_after_waiting': 'unreadable_text',
    'unexpected_successor': 'bad_saved_state',
    # A plan that refuses to click until an unresolved exploration is resumed is a
    # saved-state error: nothing is missing on the page, our route is stale.
    'the_exploration_must_be_resumed_before_a_node_click': 'bad_saved_state',
}


def kind_of(*, reason=None, stopped_reason=None, plan_reason=None):
    """The kind of one refusal, from whichever of its three names it carries.

    A recovery is triggered from three different call sites that each name the
    same refusal differently (`reason`, `stopped_reason`, `plan_reason`).  Reading
    only one of them left every historical recovery unnamed, so the action table
    never decided anything.  Precedence is most-specific first; unknown is None.
    """
    from .reason_kinds import kind_for

    for name in (reason, stopped_reason, plan_reason):
        kind = REFUSALS.get(name, STOP_KINDS.get(name))
        if kind is None:
            # The two literal tables only ever held the names somebody remembered to add.
            # `reason_kinds.kind_for` classifies *every* failure name by meaning, so a
            # page-specific sentence now inherits its class's action instead of holding.
            kind = kind_for(name)
        if kind is not None:
            return kind
    return None


REFUSALS = {
    'battle_assignment_observe_only': 'refused_by_policy',
    'battle_button_not_anchored': 'missing_control',
    'battle_has_no_proven_control': 'missing_control',
    'battle_result_control_not_anchored': 'missing_control',
    'battle_tip_dismiss_not_anchored': 'missing_control',
    'battle_victory_confirm_not_anchored': 'missing_control',
    'candidate_index_out_of_range': 'refused_by_policy',
    'continue_button_not_anchored': 'missing_control',
    'control_is_forbidden': 'missing_control',
    'cutscene_skip_not_anchored': 'missing_control',
    'defeat_accept_row_not_anchored': 'missing_control',
    'defeat_confirm_not_anchored': 'missing_control',
    'defeat_retries_exhausted': 'attempts_exhausted',
    'defeat_retry_row_not_anchored': 'missing_control',
    'deployment_battle_button_not_anchored': 'missing_control',
    'deployment_clear_selection_not_anchored': 'missing_control',
    'deployment_reset_pending_intent_not_proven': 'missing_control',
    'drive_button_not_anchored': 'missing_control',
    'dungeon_team_confirm_not_anchored': 'missing_control',
    'ego_gift_popup_confirm_not_anchored': 'missing_control',
    'enter_button_not_anchored': 'missing_control',
    'entry_confirm_button_not_anchored': 'missing_control',
    'entry_enter_button_not_anchored': 'missing_control',
    'event_check_commence_not_anchored': 'missing_control',
    'event_check_ready_continue_not_anchored': 'missing_control',
    'event_check_result_panel_not_anchored': 'missing_control',
    'event_choice_index_out_of_range': 'refused_by_policy',
    'event_result_continue_not_anchored': 'missing_control',
    'event_result_story_panel_not_anchored': 'missing_control',
    'expired_session_confirm_not_anchored': 'missing_control',
    'gift_get_confirm_not_anchored': 'missing_control',
    'gift_pick_card_not_anchored': 'missing_control',
    'gift_pick_cards_exhausted_without_a_lit_select': 'attempts_exhausted',
    'gift_pick_select_not_anchored': 'missing_control',
    'gift_search_forgo_confirm_not_anchored': 'missing_control',
    'gift_warning_cancel_not_anchored': 'missing_control',
    'grace_transaction_not_proven': 'missing_control',
    'graces_enter_not_anchored': 'missing_control',
    'hard_difficulty_not_proven': 'missing_control',
    'heal_sinners_option_not_anchored': 'missing_control',
    'initial_gift_select_not_anchored': 'missing_control',
    'initial_gift_selection_incomplete': 'no_candidate',
    'level_warning_confirm_not_anchored': 'missing_control',
    'mirror_menu_node_not_registered': 'missing_control',
    'no_candidate_node_observed': 'no_candidate',
    'no_event_check_candidate_observed': 'no_candidate',
    'no_event_choice_observed': 'no_candidate',
    'owned_gift_refuse_control_missing': 'missing_control',
    'page_is_observe_only': 'refused_by_policy',
    'pass_level_up_confirm_not_anchored': 'missing_control',
    'resume_button_not_anchored': 'missing_control',
    'reward_card_box_not_anchored': 'missing_control',
    'reward_card_confirm_not_anchored': 'missing_control',
    'run_claim_button_not_anchored': 'missing_control',
    'run_reward_bonus_cancel_not_anchored': 'missing_control',
    'run_reward_bonus_confirm_not_anchored': 'missing_control',
    'run_reward_claim_not_anchored': 'missing_control',
    'run_reward_confirm_not_anchored': 'missing_control',
    'saved_deployment_order_invalid': 'bad_saved_state',
    'saved_deployment_sequence_not_proven': 'missing_control',
    'shop_leave_button_not_anchored': 'missing_control',
    'shop_leave_confirm_not_anchored': 'missing_control',
    'star_cancel_not_anchored': 'missing_control',
    'star_confirm_button_not_anchored': 'missing_control',
    'starlight_conversion_off_and_cost_zero_not_proven': 'missing_control',
    'the_lost_summary_has_no_button_to_open_its_rewards': 'missing_control',
    'the_picker_asked_for_a_sinner_no_proven_loss_names': 'unreadable_text',
    'the_revived_sinners_notice_has_no_bound_leave': 'missing_control',
    'the_shop_asked_about_a_purchase_and_its_confirm_was_not_read': 'missing_control',
    'theme_pack_card_not_anchored': 'missing_control',
    'theme_pack_pull_target_not_anchored': 'missing_control',
    'tutorial_last_page_has_no_forward_control': 'missing_control',
    'tutorial_next_button_not_anchored': 'missing_control',
    'unknown_battle_assignment_mode': 'unreadable_text',
    'unknown_dialog_close_not_anchored': 'missing_control',
    'wanted_team_header_not_proven': 'missing_control',
    'weekly_reset_cancel_not_anchored': 'missing_control',
}
