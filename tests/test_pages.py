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
    """Every inline page-dispatch site in `runner.py`, counted per page name.

    D35's first version counted ``page == 'X'`` with a regex: 85 rows across 23
    names.  The same file asks the same question 125 times in five more
    spellings (``page != 'X'``, ``page in (...)``, ``settled_page in (...)``,
    ``page in CONST``, ``state.get('page')``), so the ratchet now counts the
    population instead of the spelling it happened to be written in.
    """
    return pages.dispatch_sites(
        (ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8'))


def test_the_runner_does_not_accumulate_new_page_specific_checks():
    """Ratchet: moving cases into window/pages lowers the count; adding fails.

    Measured 2026-10-23 with `pages.dispatch_sites`: 149 rows across 125 sites
    and 34 page names, against 61 rows in `window.plan_step`.  A new
    page-specific inline check in the runner is exactly the mechanism that
    produced page-by-page patching, so it must replace an existing one or edit
    this table on purpose.
    """
    overrun = pages.inline_overrun(_inline_counts())
    assert overrun == [], f'inline page dispatch grew for: {overrun}'


def test_the_ratchet_counts_more_than_the_one_spelling_it_replaced():
    """The old regex is kept as the floor: the population must stay bigger.

    Without this, a future edit could narrow the detector back to `page == 'X'`
    and the suite would still be green -- which is how the first ratchet managed
    to guard two thirds of the surface it described.
    """
    source = (ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    one_spelling = len(re.findall(r"page\s*==\s*'([A-Z][A-Z0-9_]*)'", source))
    counted = sum(pages.dispatch_sites(source).values())
    assert counted > one_spelling, (counted, one_spelling)
    assert counted - one_spelling >= 40, 'the five other spellings are the point'


@pytest.mark.parametrize('snippet, page, expected', [
    ("if page != 'MAP':\n    pass\n", 'MAP', 1),
    ("if page in ('MAP', 'SHOP'):\n    pass\n", 'MAP', 1),
    ("if page in ('MAP', 'SHOP'):\n    pass\n", 'SHOP', 1),
    ("if settled_page in WAIT_PAGES:\n    pass\n", pages.UNRESOLVED_PAGE, 1),
    ("if self.state.get('page') == 'SHOP':\n    pass\n", 'SHOP', 1),
    ("if state['page'] == 'GIFT_GET':\n    pass\n", 'GIFT_GET', 1),
    ("if 'MAP' == page:\n    pass\n", 'MAP', 1),
    ("if page in ():\n    pass\n", pages.UNRESOLVED_PAGE, 1),
])
def test_every_spelling_of_the_question_is_counted(snippet, page, expected):
    assert pages.dispatch_sites(snippet)[page] == expected


def test_a_question_about_something_else_is_not_a_page_dispatch():
    """The false positive the first draft of the detector produced: `.get` on a
    non-page key (``plan.get('availability') in (...)``) is not a page check."""
    counts = pages.dispatch_sites(
        "if plan.get('availability') in ('a', 'b'):\n    pass\n")
    assert counts == {}


def test_a_new_site_in_an_invisible_form_trips_the_real_ratchet():
    """The counter-example: the whole file plus one `page in (...)` site -- the
    form the first ratchet never saw -- and the failure names the page."""
    source = (ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    grown = pages.dispatch_sites(
        source + "\ndef _extra(page):\n    return page in ('MAP',)\n")
    assert pages.inline_overrun(grown) == ['MAP']


def test_the_window_chain_is_ratcheted_too():
    """A page moved out of the runner's chain and into this one is the same
    growth one module later, so the move has to show up in a diff."""
    counts = pages.dispatch_sites(WINDOW.read_text(encoding='utf-8'))
    assert pages.window_overrun(counts) == 0, pages.window_overrun(counts)
    assert pages.INLINE_WINDOW > 0
    assert pages.window_overrun({'MAP': pages.INLINE_WINDOW}) == 0
    assert pages.window_overrun({'MAP': pages.INLINE_WINDOW + 1}) == 1
    assert pages.window_overrun({'MAP': 1}) == 0


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


def test_a_click_replaced_before_the_page_settled_is_named_not_dropped():
    """The invariant the 2026-10-22 live run broke: 3 clicks, 1 verdict."""
    from maalimbus.pages import superseded_click
    assert superseded_click([1329, 307, 190, 190], [1152, 521, 190, 190]) is True
    assert superseded_click([1329, 307, 190, 190], [1329, 307, 190, 190]) is False
    assert superseded_click(None, [1, 2, 3, 4]) is False
    assert superseded_click([], [1, 2, 3, 4]) is False
