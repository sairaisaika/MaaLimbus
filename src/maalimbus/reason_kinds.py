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
