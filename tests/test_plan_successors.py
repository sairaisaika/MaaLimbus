"""A landing the archive saw every time is a page the plan is missing, not a surprise.

`expect` is a set of *names that do not disprove the input*.  A plan that names three
pages and is followed by a fourth one, every single time, is not being surprised by the
game -- it is missing a line, and the loop pays for it with ``unexpected_successor`` and a
recovery ladder instead of the next step.  D58 measured the two worst cases:

* ``the_exploration_must_be_resumed_before_a_node_click`` reached ``DUNGEON_PROGRESS``
  55 times out of 55 while the plan named only ``MAP`` and ``UNKNOWN``;
* ``mirror_menu_recognition_owns_the_click_box`` reached ``RESUME_DIALOG`` 35 times out of
  58 -- the page the five failing runs of 2026-10-23 15:33-16:32 were sitting on.

Both are now named by the plans that own them.  The rest of the archive's unnamed
landings are declared in :data:`maalimbus.pages.SUCCESSORS_THE_ARCHIVE_SAW` with their
counts, and this file is the gate: a landing that appears without being declared fails.
"""
from __future__ import annotations

import pytest

from maalimbus import pages, plan_outcomes, window

BOX = (880, 520, 160, 48)


def _entry(successors=None, intents=0):
    return {'intents': intents, 'successors': dict(successors or {})}


def _plan(page, **kwargs):
    return window.plan_step(page, **kwargs)


def test_the_resume_click_accepts_the_progress_panel():
    """The 55-of-55 landing: the resume opens the panel it then continues from."""
    plan = _plan('MAP', controls={'map.progress_button': BOX}, candidates=[BOX])
    assert plan['reason'] == 'the_exploration_must_be_resumed_before_a_node_click'
    assert window.successor_ok(plan, 'DUNGEON_PROGRESS') is True
    assert window.successor_ok(plan, 'MAP') is True


def test_the_resume_click_does_not_accept_any_page_at_all():
    """Counter-example: naming one page is not the same as accepting every page."""
    plan = _plan('MAP', controls={'map.progress_button': BOX}, candidates=[BOX])
    assert window.successor_ok(plan, 'SHOP') is False
    assert window.successor_ok(plan, 'BATTLE_HUD') is False


def test_the_mirror_menu_click_accepts_the_resume_dialog():
    """The 35-of-58 landing, and the page the five failing runs were frozen on."""
    plan = _plan('DRIVE', nodes={'DRIVE': 'MirrorDrive'})
    assert plan['reason'] == 'mirror_menu_recognition_owns_the_click_box'
    assert window.successor_ok(plan, 'RESUME_DIALOG') is True
    assert window.successor_ok(plan, 'HOME') is False


def test_a_plan_that_proves_by_dismissal_forgets_nothing():
    """A plan carrying `expect=(ANY,)` never named a page, so it cannot be missing one.

    This is the bug the first draft of ``unnamed_landings`` had: it compared every landing
    against an empty name set and offered seventeen "missing successors" to plans whose
    proof is the dismissal itself.
    """
    found = {'a_word_proven_by_dismissal': _entry({'EVENT_CHOICE': 9, 'MAP': 4}, 13)}
    declared = {'a_word_proven_by_dismissal': set()}
    assert plan_outcomes.unnamed_landings(found, declared) == []


def test_a_landing_at_an_unreadable_page_is_reported_apart():
    """Naming UNKNOWN would hide a perception failure behind a legitimate landing."""
    found = {'a_word': _entry({'UNKNOWN': 9}, 9)}
    declared = {'a_word': {'MAP'}}
    assert plan_outcomes.unnamed_landings(found, declared) == []
    rows = plan_outcomes.unreadable_landings(found)
    assert rows == [{'word': 'a_word', 'page': 'UNKNOWN', 'count': 9, 'intents': 9}]


def test_a_landing_below_the_floor_is_not_declared():
    found = {'a_word': _entry({'SHOP': 2}, 2)}
    assert plan_outcomes.unnamed_landings(found, {'a_word': {'MAP'}}) == []
    assert plan_outcomes.unnamed_landings(found, {'a_word': {'MAP'}},
                                          floor=2)[0]['page'] == 'SHOP'


def test_a_new_landing_would_fail_the_gate():
    """Counter-example for the gate itself: an undeclared landing is reported."""
    found = {'a_word_nobody_declared': _entry({'SHOP': 7}, 7)}
    rows = plan_outcomes.unnamed_landings(found, {'a_word_nobody_declared': {'MAP'}})
    assert [(row['word'], row['page'], row['count']) for row in rows] == [
        ('a_word_nobody_declared', 'SHOP', 7)]


def test_the_declaration_only_names_pages_the_loop_knows():
    for word, seen in pages.SUCCESSORS_THE_ARCHIVE_SAW.items():
        assert seen, word
        for page, count in seen.items():
            assert page in pages.PAGES, (word, page)
            assert page not in plan_outcomes.UNREADABLE, (word, page)
            assert count >= plan_outcomes.UNANIMOUS_FLOOR, (word, page, count)


def test_the_declaration_does_not_name_a_page_the_plan_already_names():
    """A declared landing the plan already names is a stale row, not a gap."""
    from maalimbus import plan_reasons

    acting = plan_reasons.acting_plans()
    for word, seen in pages.SUCCESSORS_THE_ARCHIVE_SAW.items():
        named = set((acting.get(word) or {}).get('expect_names') or ())
        stale = sorted(set(seen) & named)
        assert stale == [], (word, stale)


def test_the_archive_and_the_declaration_agree():
    """The real relation, over the retained archive; skipped when there is none."""
    found = plan_outcomes.outcomes()
    if not found:
        pytest.skip('no retained run carries a plan word')
    rows = plan_outcomes.unnamed_landings(found)
    archive = {(row['word'], row['page']): row['count'] for row in rows}
    declared = {(word, page): count for word, seen in pages.SUCCESSORS_THE_ARCHIVE_SAW.items()
                for page, count in seen.items()}
    assert archive == declared
