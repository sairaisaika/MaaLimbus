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
    # A scene loader runs no control: the page is a duration, and the loop
    # waits on it without spending the no-progress budget (D120).
    'LOADING': ('vision', 'wait'),
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
#:
#: **This is prose, and prose is not the contract** (D45, 2026-10-23).  No code
#: reads this dictionary -- it is documentation next to the table, useful when a
#: reader needs the intent in words.  ``DISPATCH_FACTS`` above is the machine
#: copy of the same questions for every page the chain plans, derived from the
#: chain itself; when the two disagree, the recorded derivation wins and the
#: page is added to ``tests/test_page_contracts.py``'s drift gate.  Two entries
#: here had already drifted from the code: ``MAP`` claimed three allowed inputs
#: where the chain offers one verb (``CLICK``) across nineteen successors, and
#: ``SHOP`` was written as a planned page although the window never plans it
#: (its inputs live in ``INLINE_RUNNER['SHOP']``).
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
    '?': 14,
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

#: The same count for ``window.py``: **34 sites**, the chain ``window.plan_step``
#: walks before the runner sees a page.  It is ratcheted too, because a page moved
#: out of the runner's chain and into this one is the same page-by-page growth one
#: module later -- the move is allowed, it just has to show up in a diff instead of
#: in a stop.  The baseline was 61 until D47 moved the 27 single-shape branches into
#: ``window.STEP_ROWS``; a ratchet that may only be raised is a counter, not a bound.
INLINE_WINDOW = 35  # D120: the loader page's own branch is the 35th



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

#: What every page in the window chain may do, derived from the chain itself by
#: :func:`window.dispatch_facts` (2026-10-23).  ``CONTRACTS`` below answers the
#: same questions in prose and nothing reads it: by the time these answers were
#: derived, ``MAP``'s entry claimed three inputs where the chain offers one verb,
#: and ``SHOP`` was written as a planned page although its inputs live in the
#: runner (``INLINE_RUNNER['SHOP']``).  Prose cannot be the contract, so this is
#: the machine copy: regenerate it from the chain, and
#: ``tests/test_page_contracts.py`` fails when the two drift apart.
#: ``'<expr>'`` is a name the chain chooses at runtime; the number of those is
#: ratcheted in the same test.
#: What every page in the window chain may do, derived from the chain itself by
#: :func:`window.dispatch_facts` (2026-10-23).  ``CONTRACTS`` below answers the
#: same questions in prose and nothing reads it: by the time these answers were
#: derived, ``MAP``'s entry claimed three inputs where the chain offers one verb,
#: and ``SHOP`` was written as a planned page although its inputs live in the
#: runner (``INLINE_RUNNER['SHOP']``).  Prose cannot be the contract, so this is
#: the machine copy: regenerate it from the chain, and
#: ``tests/test_page_contracts.py`` fails when the two drift apart.
#: ``'<expr>'`` is a name the chain chooses at runtime; the number of those is
#: ratcheted in the same test.
DISPATCH_FACTS = {
    # D120: a named loader is waited on; its refusal is the wait's own reason.
    'LOADING': {'actions': (), 'expects': (),
                'refusals': ('the_game_is_loading_the_next_scene',)},
    'BATTLE_DEFEAT': {'actions': ('CLICK',),
                      'expects': ('*',),
                      'refusals': ('defeat_accept_row_not_anchored',
                                   'defeat_confirm_not_anchored',
                                   'defeat_retries_exhausted',
                                   'defeat_retry_row_not_anchored')},
    'BATTLE_RESULT': {'actions': (), 'expects': (), 'refusals': ('battle_result_control_not_anchored',)},
    'BATTLE_TIP': {'actions': ('CLICK',), 'expects': ('*',), 'refusals': ('battle_tip_dismiss_not_anchored',)},
    'BATTLE_VICTORY': {'actions': ('CLICK',), 'expects': ('*',), 'refusals': ('battle_victory_confirm_not_anchored',)},
    'CUTSCENE': {'actions': ('CLICK',),
                 'expects': ('*', 'CUTSCENE'),
                 'refusals': ('cutscene_skip_not_anchored',)},
    'DEPLOYMENT': {'actions': ('CLICK',),
                   'expects': ('BATTLE_HUD', 'UNKNOWN'),
                   'refusals': ('deployment_battle_button_not_anchored',)},
    'DEPLOYMENT_RESET': {'actions': ('CLICK',),
                         'expects': ('PRE_BATTLE_TEAM',),
                         'refusals': ('deployment_reset_pending_intent_not_proven',)},
    'DRIVE': {'actions': ('NODE',),
              'expects': ('DRIVE', 'EXPIRED_SESSION', 'MAP', 'MIRROR_ENTRY', 'RESUME_DIALOG',
                          'THEME_PACKS', 'UNKNOWN'),
              'refusals': ('mirror_menu_node_not_registered',)},
    'DUNGEON_PROGRESS': {'actions': ('CLICK',), 'expects': ('*', 'MAP'), 'refusals': ('continue_button_not_anchored',)},
    'DUNGEON_TEAM': {'actions': ('CLICK', 'SWIPE'),
                     'expects': ('*',
                                 'DUNGEON_TEAM',
                                 'INITIAL_GIFTS',
                                 'LEVEL_WARNING',
                                 'MAP',
                                 'STAR_GRACES',
                                 'THEME_PACKS',
                                 'UNKNOWN'),
                     'refusals': ('<expr>', 'dungeon_team_confirm_not_anchored', 'wanted_team_header_not_proven')},
    'EGO_GIFT_POPUP': {'actions': ('CLICK',),
                       'expects': ('MAP', 'NODE_PANEL', 'UNKNOWN'),
                       'refusals': ('ego_gift_popup_confirm_not_anchored',)},
    'ENTRY_CONFIRM': {'actions': ('CLICK',),
                      'expects': ('DUNGEON_TEAM',
                                  'INITIAL_GIFTS',
                                  'LEVEL_WARNING',
                                  'MAP',
                                  'RESUME_DIALOG',
                                  'STAR_GRACES',
                                  'THEME_PACKS',
                                  'UNKNOWN'),
                      'refusals': ('entry_confirm_button_not_anchored',)},
    'EVENT_CHECK': {'actions': ('CLICK',),
                    'expects': ('*',
                                'CUTSCENE',
                                'EVENT_CHECK',
                                'EVENT_CHECK_RESULT',
                                'EVENT_RESULT',
                                'EVENT_RESULT_READY'),
                    'refusals': ('event_check_commence_not_anchored', 'no_event_check_candidate_observed')},
    'EVENT_CHECK_READY': {'actions': ('CLICK',),
                          'expects': ('*',),
                          'refusals': ('event_check_ready_continue_not_anchored',)},
    'EVENT_CHECK_RESULT': {'actions': ('CLICK',),
                           'expects': ('*', 'EVENT_CHECK_RESULT'),
                           'refusals': ('event_check_result_panel_not_anchored',)},
    'EVENT_CHOICE': {'actions': ('CLICK',),
                     'expects': ('*', 'EVENT_CHOICE'),
                     'refusals': ('event_choice_index_out_of_range', 'no_event_choice_observed')},
    'EVENT_RESULT': {'actions': ('CLICK',),
                     'expects': ('*',),
                     'refusals': ('event_result_story_panel_not_anchored',)},
    'EVENT_RESULT_READY': {'actions': ('CLICK',),
                           'expects': ('*', 'EVENT_RESULT_READY'),
                           'refusals': ('event_result_continue_not_anchored',)},
    'EXPIRED_SESSION': {'actions': ('CLICK',),
                        'expects': ('*',),
                        'refusals': ('expired_session_confirm_not_anchored',)},
    'EXPLORATION_COMPLETE': {'actions': ('CLICK',),
                             'expects': ('*',),
                             'refusals': ('the_lost_summary_has_no_button_to_open_its_rewards',)},
    'GIFT_GET': {'actions': ('CLICK',),
                 'expects': ('GIFT_GET',
                             'GIFT_PICK',
                             'GIFT_SEARCH',
                             'MAP',
                             'REWARD_CARD',
                             'SHOP',
                             'SHOP_PURCHASE',
                             'THEME_PACKS',
                             'UNKNOWN'),
                 'refusals': ('gift_get_confirm_not_anchored',)},
    'GIFT_PICK': {'actions': ('CLICK',),
                  'expects': ('*', 'GIFT_GET', 'GIFT_PICK', 'GIFT_WARNING', 'MAP', 'REWARD_CARD', 'UNKNOWN'),
                  'refusals': ('gift_pick_card_not_anchored',
                               'gift_pick_cards_exhausted_without_a_lit_select',
                               'gift_pick_select_not_anchored',
                               'owned_gift_refuse_control_missing')},
    'GIFT_SEARCH': {'actions': ('CLICK',),
                    'expects': ('GIFT_SEARCH_FORGO', 'MAP', 'THEME_PACKS', 'UNKNOWN'),
                    'refusals': ('gift_search_refuse_not_anchored', 'gift_search_select_not_anchored')},
    'GIFT_SEARCH_FORGO': {'actions': ('CLICK',),
                          'expects': ('GIFT_SEARCH', 'MAP', 'THEME_PACKS', 'UNKNOWN'),
                          'refusals': ('gift_search_forgo_confirm_not_anchored',)},
    'GIFT_WARNING': {'actions': ('CLICK',),
                     'expects': ('GIFT_PICK', 'UNKNOWN'),
                     'refusals': ('gift_warning_cancel_not_anchored',)},
    'HEAL_SINNERS': {'actions': ('CLICK',),
                     'expects': ('HEAL_SINNERS', 'PRE_BATTLE_TEAM', 'REVIVE_PICK', 'SHOP', 'UNKNOWN'),
                     'refusals': ('heal_sinners_option_not_anchored',)},
    'HOME': {'actions': ('CLICK',),
             'expects': ('DRIVE', 'MAP', 'MIRROR_ENTRY', 'THEME_PACKS', 'UNKNOWN'),
             'refusals': ('drive_button_not_anchored',)},
    'INITIAL_GIFTS': {'actions': ('CLICK',),
                      'expects': ('*', 'GIFT_GET', 'MAP', 'THEME_PACKS', 'UNKNOWN'),
                      'refusals': ('initial_gift_select_not_anchored', 'initial_gift_selection_incomplete')},
    'LEVEL_WARNING': {'actions': ('CLICK',),
                      'expects': ('INITIAL_GIFTS', 'MAP', 'STAR_GRACES', 'THEME_PACKS', 'UNKNOWN'),
                      'refusals': ('level_warning_confirm_not_anchored',)},
    'MAP': {'actions': ('CLICK',),
            'expects': ('CUTSCENE',
                        'DEPLOYMENT',
                        'DUNGEON_PROGRESS',
                        'EGO_GIFT_POPUP',
                        'EVENT_CHECK',
                        'EVENT_CHECK_READY',
                        'EVENT_CHECK_RESULT',
                        'EVENT_CHOICE',
                        'EVENT_RESULT',
                        'EVENT_RESULT_READY',
                        'GIFT_GET',
                        'GIFT_PICK',
                        'MAP',
                        'NODE_PANEL',
                        'PRE_BATTLE_TEAM',
                        'REWARD_CARD',
                        'SHOP',
                        'SHOP_LEAVE',
                        'UNKNOWN',
                        'WINDOW_RESET'),
            'refusals': ('candidate_index_out_of_range', 'no_candidate_node_observed')},
    'NODE_PANEL': {'actions': ('CLICK',),
                   'expects': ('CUTSCENE',
                               'EVENT_CHOICE',
                               'EVENT_RESULT',
                               'EVENT_RESULT_READY',
                               'GIFT_PICK',
                               'MAP',
                               'PRE_BATTLE_TEAM',
                               'REWARD_CARD',
                               'SHOP',
                               'UNKNOWN',
                               'WINDOW_RESET'),
                   'refusals': ('enter_button_not_anchored',)},
    'PASS_LEVEL_UP': {'actions': ('CLICK',), 'expects': ('*',), 'refusals': ('pass_level_up_confirm_not_anchored',)},
    'PRE_BATTLE_TEAM': {'actions': ('CLICK',),
                        'expects': ('*', 'BATTLE_HUD', 'DEPLOYMENT', 'THEME_PACKS', 'UNKNOWN'),
                        'refusals': ('battle_button_not_anchored',
                                     'deployment_clear_selection_not_anchored',
                                     'saved_deployment_order_invalid',
                                     'saved_deployment_sequence_not_proven',
                                                                          'the_board_shows_a_different_saved_team_than_the_plan_deploys')},
    'RESUME_DIALOG': {'actions': ('CLICK',),
                      'expects': ('INITIAL_GIFTS', 'MAP', 'STAR_GRACES', 'THEME_PACKS', 'UNKNOWN'),
                      'refusals': ('resume_button_not_anchored',)},
    'REVIVE_DONE': {'actions': ('CLICK',),
                    'expects': ('SHOP', 'UNKNOWN'),
                    'refusals': ('the_revived_sinners_notice_has_no_bound_leave',)},
    'REVIVE_PICK': {'actions': ('CLICK',),
                    'expects': ('MAP', 'PRE_BATTLE_TEAM', 'REVIVE_DONE', 'REVIVE_PICK', 'SHOP', 'UNKNOWN'),
                    'refusals': ('the_picker_asked_for_a_sinner_no_proven_loss_names',)},
    'REWARD_CARD': {'actions': ('CLICK',),
                    'expects': ('*',),
                    'refusals': ('reward_card_box_not_anchored', 'reward_card_confirm_not_anchored')},
    'RUN_CLAIM': {'actions': ('CLICK',), 'expects': ('*',), 'refusals': ('run_claim_button_not_anchored',)},
    'RUN_REWARD_BONUS': {'actions': ('CLICK',), 'expects': ('*',), 'refusals': ('run_reward_bonus_confirm_not_anchored',)},
    'RUN_REWARD_CONFIRM': {'actions': ('CLICK',), 'expects': ('*',), 'refusals': ('run_reward_confirm_not_anchored',)},
    'RUN_REWARD_DIALOG': {'actions': ('CLICK',), 'expects': ('*',), 'refusals': ('run_reward_claim_not_anchored',)},
    'SHOP_LEAVE': {'actions': ('CLICK',),
                   'expects': ('MAP', 'UNKNOWN'),
                   'refusals': ('shop_leave_confirm_not_anchored',)},
    'SHOP_PURCHASE': {'actions': ('CLICK',),
                      'expects': ('MAP', 'SHOP', 'SHOP_PURCHASE', 'UNKNOWN'),
                      'refusals': ('the_shop_asked_about_a_purchase_and_its_confirm_was_not_read',)},
    'STAR_CONFIRM': {'actions': ('CLICK',),
                     'expects': ('*', 'INITIAL_GIFTS', 'MAP', 'STAR_GRACES', 'THEME_PACKS', 'UNKNOWN'),
                     'refusals': ('grace_transaction_not_proven',
                                  'star_cancel_not_anchored',
                                  'star_confirm_button_not_anchored',
                                  'starlight_conversion_off_and_cost_zero_not_proven')},
    'STAR_GRACES': {'actions': ('CLICK',),
                    'expects': ('*', 'INITIAL_GIFTS', 'MAP', 'STAR_CONFIRM', 'THEME_PACKS', 'UNKNOWN'),
                    'refusals': ('graces_enter_not_anchored',)},
    'THEME_PACKS': {'actions': ('CLICK', 'SWIPE'),
                    'expects': ('*',),
                    'refusals': ('hard_difficulty_not_proven',
                                 'theme_pack_card_not_anchored',
                                 'theme_pack_pull_target_not_anchored')},
    'TUTORIAL': {'actions': ('CLICK',),
                 'expects': ('*',),
                 'refusals': ('tutorial_last_page_has_no_forward_control', 'tutorial_next_button_not_anchored')},
    'UNKNOWN_DIALOG': {'actions': ('CLICK',), 'expects': ('*',), 'refusals': ('unknown_dialog_close_not_anchored',)},
    'WINDOW_RESET': {'actions': ('CLICK',), 'expects': ('*',), 'refusals': ('weekly_reset_cancel_not_anchored',)},
}

#: How many times a pre-battle page may be asked to show the saved team this run
#: deploys before the page is refused (D117).  The header is also the control, so the
#: first answer to a mismatch is to press it.  Two attempts, because the measurement
#: said so: live `packaged-mirror-20261024-114050` pressed the header four times and the
#: page did not change once, so the header is a label on this build and the real preset
#: column still has to be found.  The bound stays small while that is open.
SELECT_TEAM_TRIES = 2
RECEIPT_PRINTING_PAGE = 'GIFT_GET'


def prints_a_gift_receipt(name):
    """The only page that prints `E.G.O Gift GET!` (D150).

    A receipt can be observed nowhere else, so the rule belongs here beside the page's
    own name instead of as a page comparison inside the loop's dispatch.
    """
    return name == RECEIPT_PRINTING_PAGE


UNREADABLE_PAGE = 'UNKNOWN'
# D103: the battle screen and its skill-detail overlay are named here so the runner can
# ask about them without a page comparison of its own (D44's ratchet counts literals).
BATTLE_HUD_PAGE = 'BATTLE_HUD'
BATTLE_TIP_PAGE = 'BATTLE_TIP'


def is_battle_hud(name):
    """Is this the battle screen the plan acts on? (named here, per D44's ratchet)"""
    return name == BATTLE_HUD_PAGE


BATTLE_PAGES = ('BATTLE_HUD', 'BATTLE_PLANNING', 'BATTLE_RESULT', 'BATTLE_TIP', 'DEFEAT')


def is_battle(name):
    """Is this page part of a fight?

    Asked by D129 (an unreadable frame inside a battle is a transition, not an unknown
    page) and by the speed toggle (pressed once per fight).  Named here so the runner
    asks the vocabulary instead of comparing page literals (D44 counts them).
    """
    return str(name or '') in BATTLE_PAGES


def is_battle_tip(name):
    """Is this the skill-detail overlay that covers the battle screen?"""
    return name == BATTLE_TIP_PAGE


LOADING_PAGE = 'LOADING'


def is_loading(name):
    """Is this page the game's own scene loader?

    A loader has no control and no name to read beyond its caption, so it is a state of
    its own rather than an unreadable page (D120).  The runner asks this instead of
    comparing against a page name (D44 counts page dispatch wherever it is written).
    """
    return str(name or '') == LOADING_PAGE


def is_unreadable(name):
    """True for the page that stands for "the reader could not name this one".

    D81 asked the loop to remember the last page it *could* name, which is a question
    about the page vocabulary and not about the map or the menu.  Keeping the literal
    here is what lets `MirrorRunner.step` ask it without adding a page-specific
    comparison to the runner -- D44's ratchet failed the first draft for exactly that
    reason, and it was right.
    """
    return name == UNREADABLE_PAGE


def facts(page):
    """The recorded capabilities of one page, or ``None`` if the chain has none."""
    return DISPATCH_FACTS.get(page)


def fact_drift(derived=None):
    """Pages whose recorded capabilities differ from the chain that decides today.

    ``derived`` defaults to :func:`window.dispatch_facts`, so a caller normally
    only asks "does the record still describe the chain"; a test injects a
    mutated derivation to prove the comparison can fail.
    """
    if derived is None:
        from . import window
        derived = window.dispatch_facts()
    recorded = {page: {key: list(row[key]) for key in ('actions', 'expects', 'refusals')}
                for page, row in DISPATCH_FACTS.items()}
    drift = {}
    for page in sorted(set(recorded) | set(derived)):
        if recorded.get(page) != derived.get(page):
            drift[page] = {'recorded': recorded.get(page), 'chain': derived.get(page)}
    return drift


def unsafe_wait_branches(derived=None, wait_pages=None):
    """Declared wait pages whose branch can refuse with an action that stops a run.

    A page on the wait list clears itself, so refusing on it is allowed (the loop
    then keeps waiting instead of clicking into the page).  What is *not* allowed
    is a refusal that maps to a stopping action: that turns "this screen has no
    control" into the end of the run -- the failure mode the mandate calls 路径
    失败后容易直接停止.  Returns ``[(page, reason, kind, action), ...]``.
    """
    if wait_pages is None:
        from . import window
        wait_pages = window.WAIT_PAGES
    if derived is None:
        from . import window
        derived = window.dispatch_facts()
    stopping = [action for action in set(RECOVERY_BY_KIND.values())
                if action not in WAIT_ONLY_ACTIONS]
    unsafe = []
    for page in wait_pages:
        row = derived.get(page) or {}
        for reason in row.get('refusals', ()):
            kind = REFUSALS.get(reason)
            action = recovery_for(kind)
            if action in stopping:
                unsafe.append((page, reason, kind, action))
    return unsafe


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

# D50.  Every ending names the path that wrote it.
#
# A run can end in four ways and, measured on 2026-10-23, one of them was invisible:
# `tools/audit_runs.py` printed `stopped: 81  died_without_a_stop: 51` over 142 runs and
# the two numbers do not add up, because 10 runs ended on `mirror_loop_error` alone --
# neither a stop nor a death, so the census dropped them.  A denominator that silently
# loses runs makes every rate above it wrong.
#
# The vocabulary is closed: a writer names one of these, or the census calls the ending
# unrecorded / a death, and both of those are verdicts about a missing writer rather
# than paths anything can take.
STOP_PATHS = {
    'agent_loop': 'the agent wrapper wrote the stop after the loop returned',
    'pipeline_error': 'the loop ended its own session on a node failure and wrote the stop',
    'stall_watchdog': 'the frame watch found the page frozen and ended the process',
    'no_progress_watchdog': 'the progress watch found no event for its window and ended the process',
    'process_died': 'no ending record was written: a census verdict, not a writer',
    'unrecorded': 'an ending written before the stop path existed, so it names none',
}

# The path a writer must name.  `process_died` and `unrecorded` are deliberately absent:
# nothing may write them, they are only ever read back by the census.
STOP_PATH_WRITERS = ('agent_loop', 'pipeline_error', 'stall_watchdog', 'no_progress_watchdog')

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
    # D72: the framework tears the task down when a pipeline node fails, so there is
    # nothing left to look at or click.  The only honest recovery action is to stop this
    # run -- a fresh task is a new run, not a recovery of this one, and the viewport
    # ladder cannot reach a session that no longer exists.
    # D119: the transaction refuses to re-point a card that already has input in
    # flight, so the only honest answer is to stop before sending more (a re-order
    # after a reservation is a data question, not a recovery gesture).
    'Deployment order changed during selection': 'refused_by_policy',
    # D120: the loader is bounded by a clock, and the clock running out is a stop
    # (there is no control on a loading screen to escalate to).
    'the_loading_screen_never_left': 'refused_by_policy',
    'an_action_node_failed_and_the_task_was_torn_down': 'refused_by_policy',
    # D96: the page never became readable, so the only honest recovery is another read
    # -- which the blocked-wait budget has already refused to spend.
    'the_loop_waited_without_a_new_page': 'unreadable_text',
    # A run that ended without recording a step ended without evidence (measured on
    # `packaged-mirror-20261024-055841`): nothing here can be recovered.
    'no_step_recorded': 'refused_by_policy',
    # A submitted turn that never showed a page is a transition the run cannot
    # complete from here: the only honest action is to stop (D97/D98).
    'the_submitted_turn_never_showed_a_page': 'refused_by_policy',
    'the_battle_stayed_unreadable': 'unreadable_text',
    'the_battle_animation_never_returned_to_the_board': 'unreadable_text',
    'the_emulator_stopped_producing_new_frames': 'unreadable_text',
    # A run that ended on a bare exception class (archived: 7 rows named
    # `ValueError` from in-process tools whose exception reached the journal)
    # is a state the run itself produced, not the screen's fault.
    'ValueError': 'bad_saved_state',
    'the_budget_could_not_pay_for_another_step': 'refused_by_policy',
    'the_map_header_was_read_but_the_theme_pack_was_not': 'unreadable_text',
    # A deployment input went out and the page never confirmed it: the transaction is
    # unfinished, so the loop stops rather than guess (D116).
    'Unverified deployment input remains pending': 'refused_by_policy',
    'the_screen_never_changed_and_no_input_was_sent': 'unreadable_text',
    'the_exempt_input_repeated_without_progress': 'attempts_exhausted',
    'the_controller_route_was_lost_and_rebinding_did_not_help': 'refused_by_policy',
    # D84: a task that finished releases the controller route, so a loop that is about to
    # send input with no task running can only stop -- it cannot rebuild the task.
    'the_input_door_needs_a_task_that_owns_the_controller': 'refused_by_policy',
    # D82: the task was torn down but the page moved, so the loop kept reading; the
    # binding it would need to send input was released with the task.
    'the_controller_binding_was_released_when_the_task_was_torn_down': 'refused_by_policy',
    # Measured 2026-10-24 (`packaged-mirror-20261024-144625`): the first free gift
    # showed three outlines that could not be told apart, so the loop refused to guess.
    # A re-read is the honest recovery: the outline is a picture, not a text it can
    # re-parse, and a second look is cheaper than a wrong pick.
    'three_free_gift_outline_ambiguous': 'unreadable_text',
    # D147: the ledger knows a commit was sent and no receipt followed it.  That is a
    # saved state that does not reconcile with the screen, so the ladder is the honest
    # recovery -- a re-read or a gesture may still produce the page that prints it.
    'floor_gift_receipt_unknown_repeated_or_pending': 'bad_saved_state',
    # D147: a numpy array used as a truth test crashed one run on 2026-10-24
    # (packaged-mirror-20261024-155435); the cause is fixed, and the sentence stays
    # classified so the historical census keeps naming it instead of holding it.
    'The truth value of an array with more than one element is ambiguous. Use a.any() or a.all()': 'unreadable_text',
}

# Words a plan the *runner* assembles carries.  These plans do not pass through
# `window.plan_step`, so they inherit none of that door's bookkeeping -- and until now
# they inherited no literal kind either: `kind_of` fell through to the prose model,
# which read "refusal" inside `confirm_proven_owned_gift_refusal` and answered
# `refused_by_policy`, whose action is `stop`.  The plan clicks a target that came out
# of the record (`floor_gift_transaction.refusal_confirm_target`), so a click that
# changes nothing means the record and the screen disagree -- a saved-state error, not
# a policy refusal.  Measured 2026-10-23: exactly one such plan exists
# (`maalimbus.plan_reasons.producers()['runner']`), and the count is gated there.
PLANNED_REASONS = {
    'confirm_proven_owned_gift_refusal': 'bad_saved_state',
}


# Words whose plan sends an input and whose only proof is `expect=(ANY,)`: the page
# must *change*, without saying where to.  That is a proof, and D49 mis-measured it:
# `plan_reasons._elements` drops every symbol, so `ANY` read as zero expectations and
# twenty-eight words were declared unjudgeable.  Measured 2026-10-23 after the fix --
# 80 acting plans, 45 with a named successor, 43 with a dismissal, 21 named by a runner
# hook, 0 with nothing at all.  What remains is weaker than a named successor: the loop
# learns the input landed, not where it landed, so a click that lands on the wrong page
# passes.--  The value is `page_must_change`, and `tests/test_plan_proof.py` fails when a
# new acting plan carries only that and is not declared here.
PLANS_WITH_ONLY_A_DISMISSAL = {
    'a_completed_run_spends_one_weekly_bonus_on_its_rewards': 'page_must_change',
    'a_key_saved_slot_is_dead_and_the_shop_sells_the_way_back': 'page_must_change',
    'a_lost_run_opens_its_rewards_only_to_give_them_up': 'page_must_change',
    'a_run_that_was_not_completed_keeps_the_weekly_bonus': 'page_must_change',
    'claiming_is_the_only_forward_input_on_the_run_summary': 'page_must_change',
    'confirm_grants_the_picked_encounter_reward': 'page_must_change',
    'disable_unauthorized_starlight_conversion': 'page_must_change',
    'dungeon_team_slot_is_selected_for_the_rotation': 'page_must_change',
    'grace_card_is_bought_within_the_available_starlight': 'page_must_change',
    'the_check_outcome_is_left_with_its_lit_continue': 'page_must_change',
    'the_event_result_story_is_tapped_to_reveal_its_continue': 'page_must_change',
    'the_expired_session_is_confirmed_so_its_rewards_are_claimed': 'page_must_change',
    'the_factory_result_is_acknowledged_on_its_own_panel': 'page_must_change',
    'the_pass_level_up_notice_is_acknowledged_to_clear_the_menu': 'page_must_change',
    'the_reward_card_must_be_picked_before_confirm': 'page_must_change',
    'the_reward_claim_is_confirmed_and_never_cancelled': 'page_must_change',
    'the_reward_modal_is_claimed_and_never_given_up': 'page_must_change',
    'the_skill_detail_popup_is_dismissed_off_the_board': 'page_must_change',
    'the_suspended_exploration_is_left_for_the_entry': 'page_must_change',
    'the_suspended_exploration_is_resumed_from_the_entry': 'page_must_change',
    'the_unexpected_dialog_is_dismissed_with_its_own_close': 'page_must_change',
    # Reached through `state.get('reason') or '<this word>'` in the window layer; the
    # `or` fallback (D57) is what made it visible here, and the same plan is an `advance`
    # plan, so its click is also judged by the frame.
    'the_starting_gift_is_picked_from_the_rotation_keyword': 'page_must_change',
    # D64: visible now, always was in the code -- the row pick names its word as a
    # literal in the window layer instead of handing it over in `initial['reason']`.
    'the_starting_gift_row_is_taken_from_the_tray': 'page_must_change',
    'the_way_back_to_the_entry_is_confirmed': 'page_must_change',
    'the_weekly_reset_notice_is_declined_and_the_run_stays': 'page_must_change',
    'the_wiped_run_is_accepted_and_the_stage_select_comes_back': 'page_must_change',
    'tutorial_book_is_closed_from_its_own_header_arrow': 'page_must_change',
    'tutorial_last_page_is_closed_from_the_book_header': 'page_must_change',
    'tutorial_overlay_must_be_dismissed_before_enter_is_live': 'page_must_change',
    'victory_confirm_clears_the_result_and_carries_the_rewards': 'page_must_change',
}


# The dismissal is the *only* proof these words carry: `expect=(ANY,)` says "the page
# must change" and nothing about where it changed to.  That is weaker than a named
# successor, but it is a proof, and D49's count of it (zero, because `_elements` drops
# symbols) was the instrument's error, not the code's -- see D56.
# `maalimbus.plan_outcomes` derives the population from the source and fails when a
# declared word is not one the chain really sends with only a dismissal.


# Words the archive proves were sent, but which no static read of the plan source can
# name.  The reach of `plan_reasons` has three shapes, measured 2026-10-23:
#
#   * a concatenation of a parameter's default -- the battle page builds its reason as
#     `battle_assignment + '_is_the_proven_auto_assign_control'`, so the word depends on
#     a default argument and not on a literal;
#   * a reason that travels through a state dictionary -- the runner chooses the starting
#     gift row and hands the word over in `initial['reason']`, so the plan that sends it
#     lives in the window layer and its word in the runner's locals;
#   * a word the *archive* shows the loop logging that the source does not contain at
#     all, which this constant must not silently absorb.
#
# Being unnameable is not the same as being unjudged: the plan behind the starting-gift
# row carries `expect=(ANY,), advance=True`, i.e. a pixel proof.  So this table declares
# the index's reach, not the plan's proof, and the value is the number of sends the
# archive retained, so the size of the blind spot travels with it.
# Empty since D64: the two entries this table carried were not a limit of the *index* but
# two writers that hid their own word -- a reason built by concatenating a parameter
# (`battle_assignment + '_is_the_proven_auto_assign_control'`, 152 recorded sends) and one
# handed over through `initial['reason']` (8 sends).  Both now name their two legal words
# as literals in the window layer, so every acting plan in the repository is visible to the
# reader that gates successors.  The table stays because the gate reads it: a new
# unnameable writer must be declared here with the number of sends the archive saw.
PLANS_THE_INDEX_CANNOT_NAME = {}

# Landings the retained archive saw on a page the plan never named, while the plan *did*
# name other pages.  `expect` means "a page that does not disprove this input", so a page
# reached every time is one the plan is missing, and its absence is reported as
# `unexpected_successor` and answered with a recovery ladder instead of the next step
# (D58).  The two worst cases were fixed in the plans that own them:
#   the_exploration_must_be_resumed_before_a_node_click  MAP -> DUNGEON_PROGRESS   55 of 55
#   mirror_menu_recognition_owns_the_click_box          DRIVE -> RESUME_DIALOG    35 of 58
# -- both on the way into a run, where a false escalation fires before any gameplay, and
# the second is the page the five failing runs of 2026-10-23 15:33-16:32 were sitting on.
# What remains is inside the event/cutscene flow, where the page is transient and the next
# read usually resolves it; each row is declared with the count the archive shows, so the
# size of the gap travels with it, and the gate fails on a landing that appears here
# without being named.  Naming a page is the fix, and it needs its own evidence: adding a
# page to `expect` says only that landing there does not disprove the input.
SUCCESSORS_THE_ARCHIVE_SAW = {
    # Counts moved on 2026-10-24 after the authorised runs; D58's rule is that a landing
    # the archive saw is a missing line, so the counts follow the corpus and the rule does
    # not change.
    'the_cutscene_is_skipped_to_resume_the_run': {'EVENT_CHECK': 11, 'EVENT_CHECK_READY': 5, 'EVENT_CHECK_RESULT': 8, 'EVENT_CHOICE': 16},
    'the_event_choice_that_names_its_reward_is_taken': {'EVENT_RESULT': 8, 'EVENT_RESULT_READY': 8},
    'the_event_result_is_cleared_with_its_own_continue': {'CUTSCENE': 10, 'GIFT_GET': 3},
    'the_check_outcome_is_tapped_through_until_its_control_lights_up': {'CUTSCENE': 3, 'EVENT_CHECK_READY': 7},
    'mirror_menu_recognition_owns_the_click_box': {'STAR_GRACES': 4},    # Measured 2026-10-24 (`packaged-mirror-20261024-181536`): a battle the loop started
    # from the pre-battle page goes through the loader before its HUD.
    'battle_button_submits_the_team': {'LOADING': 3},

}

# What each rung of `runner.RECOVERY_LADDER` was observed to do to the *view*, per page.
# A rung moves the viewport, so a page change cannot measure it: D58 found 0 of 274
# recoveries landing on a different page name, which said nothing about the rungs.  The
# journal already carries the evidence (`map_observed` records the boxes the reader found),
# and the classes below are what `run_metrics.rung_effect` derives from
# `evidence/runtime/packaged-mirror-*` (2026-10-23).  The page is part of the key because
# it is part of the answer: `wait` changed the view 7 times of 9 on MAP, where the page is
# still animating, and 0 times of 38 on DRIVE, a fixed layout -- the same gesture, the
# opposite result.
#   moves_the_view   the rung changed what the reader could see in most of its spends
#   rarely           it changed something, but most spends left the frame identical
LADDER_VIEW_EVIDENCE = {
    # Measured after the 2026-10-25 in-process runs: a pinch on the loading
    # screen moved the reader's view 3 of 3 (the loader animates), so it is
    # declared like any other rung rather than left undeclared.
    ('pinch_out', 'LOADING'): 'moves_the_view',
    ('pinch_out', 'MAP'): 'moves_the_view',
    ('drag_up', 'MAP'): 'moves_the_view',
    ('pan_left', 'MAP'): 'moves_the_view',
    ('pan_right', 'MAP'): 'moves_the_view',
    ('wait', 'MAP'): 'moves_the_view',
    # Measured 2026-10-24: three of three waits on the pre-battle page moved the
    # board (the page re-renders its cards after a pause), so this rung is declared.
    ('wait', 'PRE_BATTLE_TEAM'): 'moves_the_view',
    ('drag_down', 'MAP'): 'rarely',
    ('pinch_out', 'UNKNOWN'): 'rarely',
    ('drag_down', 'UNKNOWN'): 'rarely',    # Measured 2026-10-24 (`packaged-mirror-20261024-172437`): three waits on the
    # battle page, none changed what the reader could see.
    ('wait', 'BATTLE_HUD'): 'rarely',

    ('drag_up', 'UNKNOWN'): 'moves_the_view',  # 2 of 3 live polls changed the reader's view
}

# Rungs that are supposed to move nothing: on a fixed screen the engine is only allowed the
# settle wait (`FIXED_LAYOUT_PAGES`, and pinching DRIVE once killed the task), so a zero
# change there is the design working, not a rung failing to act.
LADDER_STATIC_BY_DESIGN = {('wait', 'DRIVE')}


def ladder_view_class(changed, measured):
    """Which class a rung's own measurement puts it in.

    The boundary is a rate, not a count, so adding runs to the archive does not silently
    reclassify a rung: at least half of the measured spends changed the view, or it did
    not.  A rung measured fewer than three times is `unmeasured` -- it is not evidence.
    """
    if measured < 3:
        return 'unmeasured'
    return 'moves_the_view' if changed / measured >= 0.5 else 'rarely'


# Where the rungs are compared with their evidence.  Every rung is shared across pages, and
# MAP is the page where all of them are spent (the other pages the ladder touches are either
# fixed layouts, where only `wait` is allowed, or unreadable, where no gesture has anything
# to move), so the ordering rule is asked about MAP.
LADDER_ORDER_PAGE = 'MAP'
LADDER_SETTLE_RUNG = 'wait'


def ladder_order_problems(rungs=None):
    """Rungs placed before a rung the archive measured as better.

    A stop spends the ladder in order and most stops never reach the third rung, so the
    order *is* the policy: a rung that changed the view in one spend of four must not be
    spent before one that changed it every time.  `wait` is exempt -- it is the settle
    round, not a gesture, and it belongs last whatever its number says.
    """
    if rungs is None:
        from .runner import RECOVERY_LADDER
        rungs = [name for name, _ in RECOVERY_LADDER]
    kinds = []
    for name in rungs:
        if name == LADDER_SETTLE_RUNG:
            continue
        kinds.append((name, LADDER_VIEW_EVIDENCE.get((name, LADDER_ORDER_PAGE))))
    problems = []
    for index, (name, kind) in enumerate(kinds):
        if kind != 'rarely':
            continue
        for later, later_kind in kinds[index + 1:]:
            if later_kind == 'moves_the_view':
                problems.append((name, later))
    return problems


def kind_of(*, reason=None, stopped_reason=None, plan_reason=None):
    """The kind of one refusal, from whichever of its three names it carries.

    A recovery is triggered from three different call sites that each name the
    same refusal differently (`reason`, `stopped_reason`, `plan_reason`).  Reading
    only one of them left every historical recovery unnamed, so the action table
    never decided anything.  Precedence is most-specific first; unknown is None.
    """
    from .reason_kinds import kind_for

    for name in (reason, stopped_reason, plan_reason):
        # D146: an instrumented refusal appends its numbers after a colon
        # (`three_free_gift_outline_ambiguous:0:[]:...`), and the message is the only
        # place those numbers can travel.  Measured 2026-10-24: fifteen such strings
        # entered the census as fifteen unnamed failures.  The name is the part before
        # the first colon; the numbers stay in the record.
        head = name.split(':', 1)[0] if isinstance(name, str) else name
        kind = REFUSALS.get(head, STOP_KINDS.get(head, PLANNED_REASONS.get(head)))
        if kind is None:
            # The literal tables only ever held the names somebody remembered to add.
            # `reason_kinds.kind_for` classifies *every* failure name by meaning, so a
            # page-specific sentence now inherits its class's action instead of holding.
            kind = kind_for(head)
        if kind is not None:
            return kind
    return None


REFUSALS = {
    'battle_assignment_observe_only': 'refused_by_policy',
    'battle_button_not_anchored': 'missing_control',
    'battle_has_no_proven_control': 'missing_control',
    # A repeated mode switch cannot conjure the submit dial (D111).
    'the_submit_dial_was_not_found_after_the_assignment': 'missing_control',
    # The pair of battle inputs was taken and the board still did not advance: nothing
    # this plan can send is the missing one, so the honest class is "tried enough" and
    # the action is to wait on the board rather than to send it again (D112).
    'the_board_did_not_answer_the_pair_of_inputs': 'attempts_exhausted',
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
    'the_game_is_loading_the_next_scene': 'missing_control',
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
    # The team on the board is not the team this run deploys: nothing on this page can be
    # verified against the ledger, so it waits (D117).
    'the_board_shows_a_different_saved_team_than_the_plan_deploys': 'bad_saved_state',
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
