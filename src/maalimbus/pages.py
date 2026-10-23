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


#: Inline ``page == 'X'`` comparisons in ``runner.py``, measured 2026-10-23:
#: **88 comparisons across 24 pages**, against 52 branches in
#: ``window.plan_step``.  MAP alone is compared 22 times.  That split is what lets one page be
#: planned in one module and refused in another.
#:
#: This is a **ratchet, not a target**: the numbers may go down as cases move
#: into ``window``/``pages``, and ``tests/test_pages.py`` fails if any of them
#: goes up.  A new page-specific inline check must therefore either replace an
#: existing one or be argued for by editing this table deliberately.
INLINE_RUNNER = {
    'BATTLE_DEFEAT': 1,
    'DEPLOYMENT_RESET': 3,
    'DUNGEON_PROGRESS': 1,
    'DUNGEON_TEAM': 5,
    'EVENT_CHOICE': 1,
    'EVENT_RESULT': 2,
    'GIFT_GET': 11,
    'GIFT_PICK': 4,
    'HEAL_SINNERS': 2,
    'INITIAL_GIFTS': 3,
    'MAP': 20,
    'NODE_PANEL': 1,
    'PRE_BATTLE_TEAM': 5,
    'RESUME_DIALOG': 1,
    'REVIVE_DONE': 1,
    'REWARD_CARD': 3,
    'SHOP': 4,
    'SHOP_PURCHASE': 2,
    'STAR_CONFIRM': 1,
    'STAR_GRACES': 5,
    'THEME_PACKS': 1,
    'TUTORIAL': 3,
    'UNKNOWN': 3,
    'UNKNOWN_DIALOG': 3,
}


def inline_overrun(counts):
    """Pages whose inline checks grew past the recorded baseline."""
    return sorted(name for name, n in counts.items()
                  if n > INLINE_RUNNER.get(name, 0))


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
    'bad_saved_state': 'recompute_state',
    'refused_by_policy': 'stop',
}



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


def kind_of(*, reason=None, stopped_reason=None, plan_reason=None):
    """The kind of one refusal, from whichever of its three names it carries.

    A recovery is triggered from three different call sites that each name the
    same refusal differently (`reason`, `stopped_reason`, `plan_reason`).  Reading
    only one of them left every historical recovery unnamed, so the action table
    never decided anything.  Precedence is most-specific first; unknown is None.
    """
    for name in (reason, stopped_reason, plan_reason):
        kind = REFUSALS.get(name)
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
