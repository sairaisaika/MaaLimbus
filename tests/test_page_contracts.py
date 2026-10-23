"""The page contract is derived from the chain, and every exception is named.

``pages.CONTRACTS`` was the designed answer to "how does this page prove it was
entered, what may follow, how does it fail" and no code ever consulted it: three
of sixty pages, prose only, and by 2026-10-23 two of the three described a chain
that no longer existed (``MAP`` claimed three inputs where the chain offers one
verb; ``SHOP`` was written as a planned page although its inputs live in the
runner).  These tests pin the machine copy instead -- the derivation in
``window.dispatch_facts`` against the record in ``pages.DISPATCH_FACTS`` -- and
name the only exceptions, so a page that gains or loses a capability has to
appear in a diff.
"""
import pathlib

import pytest

from maalimbus import pages, window

DERIVED = window.dispatch_facts()
SOURCE = pathlib.Path(window.__file__).read_text(encoding='utf-8')

#: A page the registry does not plan but the chain still answers.  It is allowed
#: only while its branch is a refusal on a page that clears itself: nothing is
#: clicked on BATTLE_RESULT (it advances without input), so naming the refusal
#: keeps the missing-control diagnostic instead of falling through to the generic
#: observe-only answer.
NAMED_REFUSAL_ON_A_WAIT_PAGE = {'BATTLE_RESULT'}

#: Names the chain chooses at runtime and no reader can resolve statically.
#: ``DUNGEON_TEAM`` refuses with ``navigation['reason']``, a control-dependent
#: string.  The number may fall; it may not rise unnoticed.
UNREADABLE_BASELINE = 1


def test_the_record_matches_the_window_chain():
    assert pages.fact_drift() == {}


def test_the_drift_gate_can_fail():
    """A record that differs from the chain is drift, not a rendering detail."""
    mutated = {page: dict(row) for page, row in DERIVED.items()}
    mutated['MAP'] = dict(mutated['MAP'], expects=('SHOP',))
    assert set(pages.fact_drift(mutated)) >= {'MAP'}
    dropped = dict(DERIVED)
    del dropped['SHOP_PURCHASE']
    assert 'SHOP_PURCHASE' in pages.fact_drift(dropped)
    added = dict(DERIVED, A_PAGE_THAT_DOES_NOT_EXIST={'actions': (), 'expects': (), 'refusals': ()})
    assert 'A_PAGE_THAT_DOES_NOT_EXIST' in pages.fact_drift(added)


def test_a_branch_that_only_the_chain_knows_about_shows_up_as_drift():
    """The record is compared with the chain, so a new branch cannot hide."""
    mutated = SOURCE.replace(
        "    if page == 'MAP':",
        "    if page == 'A_NEW_PAGE':\n"
        "        return _refuse(page, 'no_candidate_node_observed')\n"
        "    if page == 'MAP':", 1)
    assert mutated != SOURCE
    derived = window.dispatch_facts(mutated)
    assert derived['A_NEW_PAGE'] == {'actions': [], 'expects': [],
                                     'refusals': ['no_candidate_node_observed']}
    assert 'A_NEW_PAGE' in pages.fact_drift(derived)


def test_every_planned_page_is_a_branch_and_the_only_extra_is_a_named_refusal():
    planned = {page for page, (_, handling) in pages.PAGES.items() if handling == 'plan'}
    assert planned - set(DERIVED) == set()
    extra = set(DERIVED) - planned
    assert extra == NAMED_REFUSAL_ON_A_WAIT_PAGE
    for page in extra:
        assert pages.PAGES[page][1] == 'wait'
        assert DERIVED[page]['actions'] == []


def test_a_wait_page_may_refuse_but_its_refusal_may_not_stop_the_run():
    assert pages.unsafe_wait_branches() == []


def test_the_wait_invariant_can_fail():
    """A refusal that maps to a stopping action on a wait page would end a run."""
    crafted = {'DEFEAT': {'actions': [], 'expects': [],
                          'refusals': ['defeat_retries_exhausted']}}
    unsafe = pages.unsafe_wait_branches(crafted, wait_pages=('DEFEAT',))
    assert unsafe == [('DEFEAT', 'defeat_retries_exhausted',
                       'attempts_exhausted', 'escalate_ladder')]


def test_a_refusal_a_wait_page_states_harmlessly_is_still_harmless():
    crafted = {'BATTLE_RESULT': {'actions': [], 'expects': [],
                                 'refusals': ['battle_result_control_not_anchored']}}
    assert pages.unsafe_wait_branches(crafted, wait_pages=('BATTLE_RESULT',)) == []


def test_every_contracted_page_has_a_machine_owner():
    """A prose contract is only allowed where the facts exist in some layer."""
    owned = set(pages.DISPATCH_FACTS) | set(pages.INLINE_RUNNER)
    assert set(pages.CONTRACTS) - owned == set()
    # SHOP is the case the derivation caught: the window never plans it, so its
    # inputs can only live in the runner's inline dispatch.
    assert 'SHOP' not in DERIVED
    assert pages.INLINE_RUNNER['SHOP'] > 0


def test_the_unreadable_names_only_get_rarer():
    unreadable = {name for row in pages.DISPATCH_FACTS.values()
                  for name in row['expects'] + row['refusals'] if name.startswith('<')}
    assert len(unreadable) <= UNREADABLE_BASELINE
    assert unreadable <= {'<expr>', '<missing>'}


def test_a_page_without_a_control_is_the_one_that_has_no_action():
    """The refusal-only branch is the whole point of the exception set."""
    silent = {page for page, row in pages.DISPATCH_FACTS.items() if not row['actions']}
    assert silent == NAMED_REFUSAL_ON_A_WAIT_PAGE
    for page in silent:
        assert pages.facts(page)['refusals'], 'a page with no action must say why'
