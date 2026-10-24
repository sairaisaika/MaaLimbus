"""One contract for "the control this page needs could not be located".

The window layer had accumulated 46 separate ``<control>_not_anchored``
refusals, one per page branch, and every one of them ended the step with a
page-specific string.  They were not really page-specific failures: they are
one mechanism (the anchor was not in the frame) reported 46 different ways, so
each new page added a new string and nothing could act on the whole class.

This module is the single place that answers three questions for that class:

* which control was missing (``anchor``),
* on which page and after which recovery rungs (``page`` / ``tried``),
* what the refusal *is* (``stop_kind``), so a caller can decide to recover
  instead of treating every missing anchor as the end of the run.

Nothing here recognises anything: it only names the failure.  The reason
strings stay byte-identical to the ones already in the ledger, so existing
evidence and tests keep working.
"""

from __future__ import annotations

SUFFIX = '_not_anchored'

#: Reasons that mean exactly the same thing as ``*_not_anchored`` but were
#: spelled differently before this contract existed.  Mapping them (rather than
#: renaming) keeps the ledger's historical text intact while making the class
#: countable: two of these were found by the guard test, not by reading code.
ALIASES = {
    'battle_has_no_proven_control': 'battle',
    # The dial is a control on the same board, so the anchor it is missing is the board's
    # (D111: live `packaged-mirror-20261024-092948`).
    'the_submit_dial_was_not_found_after_the_assignment': 'battle',
    'the_board_did_not_answer_the_pair_of_inputs': 'battle',
    'owned_gift_refuse_control_missing': 'owned_gift_refuse',
}

#: ``stop_kind`` values a caller may branch on.
ANCHOR_MISSING = 'anchor_missing'   # a control this page requires was not found
PAGE_UNREADABLE = 'page_unreadable'  # nothing on the page could be read at all
HELD = 'held'                        # refusing is the correct, evidenced outcome

#: Refusals that are *not* anchor lookups.  They keep their own kind so a
#: caller can tell "we did not see the button" from "we refuse to press it".
NON_ANCHOR = {
    'battle_assignment_observe_only': HELD,
    'candidate_index_out_of_range': HELD,
    'control_is_forbidden': HELD,
    'defeat_retries_exhausted': HELD,
    'deployment_reset_pending_intent_not_proven': HELD,
    'event_choice_index_out_of_range': HELD,
    'gift_pick_cards_exhausted_without_a_lit_select': HELD,
    'grace_transaction_not_proven': HELD,
    'hard_difficulty_not_proven': HELD,
    'initial_gift_selection_incomplete': HELD,
    'mirror_menu_node_not_registered': HELD,
    'no_candidate_node_observed': PAGE_UNREADABLE,
    'no_event_check_candidate_observed': PAGE_UNREADABLE,
    'no_event_choice_observed': PAGE_UNREADABLE,
    'page_is_observe_only': HELD,
    'saved_deployment_order_invalid': HELD,
    'saved_deployment_sequence_not_proven': HELD,
    'starlight_conversion_off_and_cost_zero_not_proven': HELD,
    'the_lost_summary_has_no_button_to_open_its_rewards': HELD,
    'the_picker_asked_for_a_sinner_no_proven_loss_names': HELD,
    'the_revived_sinners_notice_has_no_bound_leave': HELD,
    'the_shop_asked_about_a_purchase_and_its_confirm_was_not_read': HELD,
    'tutorial_last_page_has_no_forward_control': HELD,
    'unknown_battle_assignment_mode': HELD,
    'wanted_team_header_not_proven': HELD,
}


def anchor_of(reason):
    """Return the control name an anchor-miss reason is about, else None."""
    if not isinstance(reason, str):
        return None
    if reason in ALIASES:
        return ALIASES[reason]
    if not reason.endswith(SUFFIX):
        return None
    name = reason[:-len(SUFFIX)]
    return name or None


def stop_kind_of(reason):
    """Classify one refusal reason without needing the page."""
    if anchor_of(reason) is not None:
        return ANCHOR_MISSING
    return NON_ANCHOR.get(reason, HELD)


def classify_refusal(page, reason, *, tried=None):
    """The plan fields one refusal carries, in one place.

    ``tried`` is the recovery rungs already spent on this page (if any).  An
    anchor miss with nothing tried is still an anchor miss, but recording it
    lets the caller distinguish "we have not tried to look again" from "we
    looked and it is really not there".
    """
    anchor = anchor_of(reason)
    fields = {
        'reason': reason,
        'stop_kind': stop_kind_of(reason),
    }
    if anchor is not None:
        fields['anchor'] = anchor
        fields['anchor_page'] = page
    if tried:
        fields['recovery_tried'] = list(tried)
    return fields


def undeclared(reasons):
    """Reasons a caller discovered but this contract does not know.

    Used by the guard test: a new page-specific refusal that never reached
    this module shows up here instead of shipping silently.
    """
    known = set(NON_ANCHOR)
    missing = []
    for reason in reasons:
        if anchor_of(reason) is not None:
            continue
        if reason not in known:
            missing.append(reason)
    return sorted(set(missing))


def reread_allowed(plan, *, attempts, tries, observe_only=False):
    """May this refusal spend one bounded re-read instead of ending the run?

    A refusal with no target is a statement about the *frame*: nothing was sent,
    so looking again costs one interval and cannot double-spend anything.  That
    was already true for ``no_...`` reading misses and is equally true for an
    anchor miss -- the button may simply have arrived on the next frame.  What
    is **not** re-readable is a policy refusal (``held``): re-reading cannot
    change whether pressing a forbidden control is allowed.
    """
    if observe_only:
        return False
    if plan.get('target') is not None:
        return False
    if not (str(plan.get('reason', '')).startswith('no_')
            or plan.get('stop_kind') == ANCHOR_MISSING):
        return False
    return attempts + 1 < max(1, tries)
