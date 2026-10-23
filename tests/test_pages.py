"""The page registry is an index of the whole loop, not a second dispatcher."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from maalimbus import pages, window

ROOT = Path(__file__).resolve().parents[1]
VISION = ROOT / 'src' / 'maalimbus' / 'vision.py'
AGENT = ROOT / 'agent' / 'recognition.py'
WINDOW = ROOT / 'src' / 'maalimbus' / 'window.py'


def _vision_names():
    return set(re.findall(r"return '([A-Z][A-Z0-9_]*)'", VISION.read_text(encoding='utf-8')))


def _agent_names():
    text = AGENT.read_text(encoding='utf-8')
    found = set(re.findall(r"scene\s*=\s*'([A-Z][A-Z0-9_]*)'", text))
    found |= set(re.findall(r"scene\s*==\s*'([A-Z][A-Z0-9_]*)'", text))
    return found


def _window_branches():
    return set(re.findall(r"page\s*==\s*'([A-Z][A-Z0-9_]*)'", WINDOW.read_text(encoding='utf-8')))


def test_every_classified_page_is_registered():
    """A new `return 'X'` in classify() must be indexed, or the guard fails."""
    assert pages.undeclared(_vision_names()) == []


def test_every_agent_scene_is_registered():
    assert pages.undeclared(_agent_names()) == []


def test_every_window_branch_is_registered():
    assert pages.undeclared(_window_branches()) == []


def test_a_planned_page_is_not_declared_runner_owned():
    """A page with a window branch cannot also be claimed by the runner."""
    claimed = set(pages.by_handling('runner'))
    assert _window_branches() & claimed == set()


def test_wait_and_observe_handling_match_the_window_layer():
    """The registry mirrors the lists that actually drive the planner."""
    # UNKNOWN and BATTLE_RESULT are listed in *both* width lists; the registry
    # records the stronger one (wait) and the overlap is a known duplication.
    for name in window.WAIT_PAGES:
        assert pages.handling(name) == 'wait'
    for name in set(window.OBSERVE_ONLY) - set(window.WAIT_PAGES):
        assert pages.handling(name) == 'observe'


def test_the_unregistered_guard_catches_a_new_page():
    """Counter-example: the guard is not vacuous."""
    assert pages.undeclared(['BRAND_NEW_PAGE']) == ['BRAND_NEW_PAGE']


def test_a_page_produced_twice_is_recorded_as_such():
    """MAP is emitted by the agent, not by `classify` -- one of the splits."""
    assert set(pages.producers('MAP')) == {'agent'}


@pytest.mark.parametrize('name', ['BATTLE_HUD', 'MIRROR_ENTRY'])
def test_runner_owned_pages_are_named(name):
    """The pages the window table does not own are countable, not invisible."""
    assert pages.handling(name) == 'runner'


def test_the_unreachable_observe_names_are_documented():
    """Two OBSERVE_ONLY entries no producer emits: recorded, not silently kept.

    Measured 2026-10-23 by grepping both producers for the literal.  If a
    producer ever starts emitting one, the registry row must change from
    'unknown' and this test tells the next reader to delete the exemption.
    """
    for name in pages.UNREACHABLE:
        assert pages.producers(name) == ['unknown']
        assert pages.handling(name) == 'observe'


# -- the inline-dispatch ratchet -------------------------------------------

def _inline_counts():
    import collections
    text = (ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    return collections.Counter(
        re.findall(r"page\s*==\s*'([A-Z][A-Z0-9_]*)'", text))


def test_the_runner_does_not_accumulate_new_page_specific_checks():
    """Ratchet: moving cases into window/pages lowers the count; adding fails.

    Measured 2026-10-23: 88 inline comparisons across 24 pages against 52
    branches in `window.plan_step`.  A new page-specific `page == 'X'` in the
    runner is exactly the mechanism that produced page-by-page patching, so it
    must replace an existing one or edit this table on purpose.
    """
    overrun = pages.inline_overrun(_inline_counts())
    assert overrun == [], f'inline page dispatch grew for: {overrun}'


def test_the_ratchet_is_not_vacuous():
    assert pages.inline_overrun({'MAP': pages.INLINE_RUNNER['MAP'] + 1}) == ['MAP']


def test_the_ratchet_allows_the_count_to_fall():
    assert pages.inline_overrun({'MAP': 1}) == []


# -- the per-page contract table -------------------------------------------

CONTRACT_FIELDS = ('entry_evidence', 'allowed_inputs', 'success_proof',
                   'failure_handling', 'irreversible')


def test_every_contract_names_a_registered_page():
    assert pages.undeclared(pages.CONTRACTS) == []


@pytest.mark.parametrize('name', sorted(pages.CONTRACTS))
def test_a_contract_answers_all_four_questions(name):
    row = pages.CONTRACTS[name]
    for field in CONTRACT_FIELDS:
        assert field in row, f'{name} does not declare {field}'
        value = row[field]
        assert value not in ('', None), f'{name}.{field} is empty'


@pytest.mark.parametrize('name', sorted(pages.CONTRACTS))
def test_a_contract_names_what_cannot_be_undone(name):
    """`irreversible` may be empty, but it must be a decision, not an omission."""
    assert isinstance(pages.CONTRACTS[name]['irreversible'], tuple)


def test_the_dead_lock_pages_all_have_a_contract():
    """The three pages that stopped live runs most often are written down."""
    for name in ('MAP', 'SHOP', 'DUNGEON_PROGRESS'):
        assert name in pages.CONTRACTS
