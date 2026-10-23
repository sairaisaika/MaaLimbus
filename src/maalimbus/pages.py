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
