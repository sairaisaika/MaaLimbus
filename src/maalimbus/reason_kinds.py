"""Six classes, not 189 names.

Every reason-like string in this repository is a human sentence about *what was
observed*.  The recovery engine only needs to know *what kind of thing went wrong*,
because that (and nothing else) selects the action.  This module is the single place
where one becomes the other.

Rules are ordered: the first matching pattern wins.  They are deliberately coarse and
explain why a name belongs to a class in one clause.  Anything that matches nothing
stays `None` on purpose -- an unmatched name is a name nobody has classified, and the
ratchet in `tests/test_stop_kinds.py` keeps that number falling.

Measured 2026-10-23 before this module existed: 189 reason-like literals, 2 mapped.
"""
import re

# (pattern, kind, why)
RULES = (
    (r'never_answered|did_not_answer|no_answer', 'unreadable_text',
     'the page was asked and never replied; re-reading is the only safe response'),
    (r'unreadable|reread|re-?read|new_pixels|ocr|could_not_read|unread', 'unreadable_text',
     'the reading itself is in doubt, so the text is what must be redone'),
    (r'resumed|resume|stale|dead|saved|restore|another_rotation|overwrite_', 'bad_saved_state',
     'our own remembered state is out of date, not the page'),
    (r'unvisited|no_candidate|candidates|nothing_left|no_node|not_observed|no_page', 'no_candidate',
     'there is no target to act on yet; the view must be moved to find one'),
    (r'not_full|cannot_start|incomplete|need_|requires?_|before_|must_|missing|no_control', 'missing_control',
     'a control the step needs is not present or not usable yet'),
    (r'exhaust|attempts?|retries|tries|budget|deadline|rounds?', 'attempts_exhausted',
     'the budget for this action is spent, so escalation rather than repetition'),
    (r'forfeit|give_?up|not_authorized|unauthori[sz]ed|refus|policy|banned|protected', 'refused_by_policy',
     'the action is not permitted, so no gesture or retry can make it legal'),
)

# Names that match a rule by accident and are known to belong elsewhere.
EXCEPTIONS = {
    # its subject is a *catalogue*, not a page reading
    'Source revision coverage requires live catalogue reconciliation': 'missing_control',
    'ambiguous_catalogue_alias': 'bad_saved_state',
    # nothing on the shelf satisfies the plan *yet*: waiting for a refresh, not a failure
    'no_offer_matches_the_gift_plan_yet': 'no_candidate',
    # the successor of a skill replacement was never confirmed; same class as unverified_*
    'skill_successor_unproven': 'bad_saved_state',
}

_COMPILED = tuple((re.compile(pattern), kind, why) for pattern, kind, why in RULES)


def kind_for(name):
    """The class of one reason-like name, or None when nobody has classified it."""
    if not isinstance(name, str) or not name:
        return None
    if name in EXCEPTIONS:
        return EXCEPTIONS[name]
    for pattern, kind, _why in _COMPILED:
        if pattern.search(name):
            return kind
    return None


def why_for(kind):
    for _pattern, candidate, why in _COMPILED:
        if candidate == kind:
            return why
    return ''


# --- role first, class second ------------------------------------------------
# A third of the 189 names are not failures at all: they are *plan intents*
# ("battle_button_submits_the_team", "a_full_party_leaves_by_its_own_button").  Feeding
# those into the failure table asks "which recovery does this failure need?" about a
# sentence that describes a deliberate action, which is why the ratio looked hopeless.
# Classifying the role first is the architectural correction; the classes only apply to
# names that actually report a failure.
INTENT_RULES = (
    r'_(is|are|submits|leaves|opens|spends|keeps|moves|counts|draws|waits|pays|costs|becomes|starts|ends|names|records|reads|writes)_',
    r'^(a|the|an)_.*_(must|should|can|cannot|will)_',
)

OUTCOME_RULES = (
    r'^the_click_opened_the_next_page$',
    r'^the_party_moved_after_the_click$',
    r'^the_page_stayed_on_the_map_after_the_click$',
    r'^the_party_did_not_move_after_the_click$',
    r'^a_new_target_replaced_this_one_before_the_page_settled$',
)

_INTENT = tuple(re.compile(pattern) for pattern in INTENT_RULES)
_OUTCOME = tuple(re.compile(pattern) for pattern in OUTCOME_RULES)


def role_of(name):
    """'outcome', 'intent', 'failure', or None when unclassified."""
    if not isinstance(name, str) or not name:
        return None
    for pattern in _OUTCOME:
        if pattern.search(name):
            return 'outcome'
    for pattern in _INTENT:
        if pattern.search(name):
            return 'intent'
    return 'failure'

# Imperative action names ("close_known_overlay_with_its_own_header_arrow",
# "win_rate_auto_assign") describe what the loop will *do*; they are intents that never
# had a verb in the middle of the sentence, which the pattern above required.
ACTION_VERBS = frozenset("""
close confirm claim pick open leave enter select assign return use buy sell fuse enhance
heal equip resume advance dismiss tap click press start submit finish take give refuse
cancel accept acknowledge skip scan read write victory settle collect
""".split())

FAILURE_MARKERS = (
    'not_', '_not', 'never', 'no_', 'cannot', 'missing', 'unknown', 'unread',
    'too_', 'exhaust', 'failed', 'invalid', 'unresolved', 'absent', 'incomplete',
    'refus', 'blocked', 'unproven', 'unavailable', 'unsupported', 'stale', 'dead',
    'require', 'must', 'need', 'short', 'budget', 'without', 'before_', 'after_',
)


def _looks_like_failure(name):
    lowered = name.lower()
    return any(marker in lowered for marker in FAILURE_MARKERS)


def role_of(name):
    """'outcome', 'intent', 'failure', or None when unclassified (later definition wins)."""
    if not isinstance(name, str) or not name:
        return None
    for pattern in _OUTCOME:
        if pattern.search(name):
            return 'outcome'
    for pattern in _INTENT:
        if pattern.search(name):
            return 'intent'
    if name.split('_', 1)[0].lower() in ACTION_VERBS and not _looks_like_failure(name):
        return 'intent'
    return 'failure'


# --- the shop / skill planner and the stillness classifier, mapped by hand ---------
# These are the last names whose class a pattern cannot decide honestly.  Each rule below
# names the reason it applies; anything still unmatched stays None and the ratchet in
# tests/test_reason_provenance.py keeps that number falling.
LATE_RULES = (
    (r'^(skill|shop|gift)_[a-z_]*unknown$', 'unreadable_text',
     'a field of the offer could not be read, so the reading is what must be redone'),
    (r'^(skill|shop|gift)_[a-z_]*(unavailable|no_gain|mismatch|not_bound|same_as)',
     'refused_by_policy',
     'the offer was read but does not satisfy the purchase policy, so no retry helps'),
    (r'^(skill|shop|gift)_[a-z_]*(unaffordable|blocked|duplicate|no_offer)',
     'refused_by_policy',
     'the offer violates a budget or ownership rule the game will not let us override'),
    (r'^unverified_', 'bad_saved_state',
     'an action whose effect was never confirmed leaves our record in doubt; re-derive '
     'it from the page rather than act on it'),
    (r'^the_page_is_(frozen|expected_to_be_static)|^the_wait_was_extended',
     'attempts_exhausted',
     'the peace was measured and the budget for waiting is spent'),
    (r'^the_(screen_is_still_changing|stillness_is_a_wait|run_kept_observing)',
     'unreadable_text',
     'the screen told us nothing stable to read, so observation is what must continue'),
    (r'provider|template|observation has no size|roi smaller|anchor needs',
     'missing_control',
     'a capability or geometry the step needs is absent, not misread'),
    (r'^minimize_enemy_strength$', 'refused_by_policy',
     'a planning preference, not a failure: it declines an offer that weakens the team'),
    (r'^route_kind_unknown$', 'unreadable_text',
     'the path kind was not read, so the reading is what must be redone'),
)

_LATE = tuple((re.compile(pattern), kind, why) for pattern, kind, why in LATE_RULES)


def kind_for(name):
    """The class of one reason-like name, or None when nobody has classified it.

    Later definitions win: this one adds LATE_RULES to the patterns above.
    """
    if not isinstance(name, str) or not name:
        return None
    if name in EXCEPTIONS:
        return EXCEPTIONS[name]
    for pattern, kind, _why in _COMPILED + _LATE:
        if pattern.search(name):
            return kind
    return None


# --- the shapes the earlier patterns missed ----------------------------------------
# `caption_not_read`, `auto_assign_buttons_not_present` and `current_position_not_proven`
# survived every rule above because they say "not X" instead of "unreadable"/"missing".
# The negative form is the most common one in this repository, so it gets its own rules.
NEGATIVE_RULES = (
    (r'_not_(read|identified|registered|recogni[sz]ed|found|visible)$|_(not_)?read_', 'unreadable_text',
     'a reading that did not happen; the text is what must be redone'),
    (r'_not_present$|_not_found$|_absent$', 'missing_control',
     'a control the step needs is not on the page'),
    (r'_not_proven$|_unproven$', 'bad_saved_state',
     'a fact we believed was never confirmed, so it must be re-derived'),
    (r'_too_short$|_too_small$|_no_size$|_has_no_size$', 'unreadable_text',
     'the region was found but is not readable, so the reading is what must be redone'),
    (r'_unknown$', 'unreadable_text',
     'a field could not be read at all'),
)

_NEG = tuple((re.compile(p), k, w) for p, k, w in NEGATIVE_RULES)


def kind_for(name):
    """The class of one reason-like name, or None when nobody has classified it.

    Final definition: EXCEPTIONS, then the specific patterns, then the negative forms.
    """
    if not isinstance(name, str) or not name:
        return None
    if name in EXCEPTIONS:
        return EXCEPTIONS[name]
    for pattern, kind, _why in _COMPILED + _LATE + _NEG:
        if pattern.search(name):
            return kind
    return None
