"""The anchor contract: one class for "the control was not in the frame"."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from maalimbus import anchor

WINDOW = Path(__file__).resolve().parents[1] / 'src' / 'maalimbus' / 'window.py'

_REFUSE = re.compile(
    r"_refuse\(\s*[A-Za-z_][\w\.\[\]'\"()]*\s*,\s*(?:reason\s*=\s*)?'([a-z0-9_]+)'\s*\)")


def _refused_reasons():
    return sorted(set(_REFUSE.findall(WINDOW.read_text(encoding='utf-8'))))


def test_the_live_window_still_refuses_with_the_same_strings():
    """The contract must not rename anything the ledger already records."""
    assert 'continue_button_not_anchored' in _refused_reasons()


def test_an_anchor_reason_names_its_control():
    assert anchor.anchor_of('continue_button_not_anchored') == 'continue_button'
    assert anchor.anchor_of('star_confirm_button_not_anchored') == 'star_confirm_button'
    assert anchor.anchor_of('no_candidate_node_observed') is None


def test_an_anchor_miss_is_classified_with_its_page_and_control():
    fields = anchor.classify_refusal('DUNGEON_PROGRESS', 'continue_button_not_anchored')
    assert fields['reason'] == 'continue_button_not_anchored'
    assert fields['stop_kind'] == anchor.ANCHOR_MISSING
    assert fields['anchor'] == 'continue_button'
    assert fields['anchor_page'] == 'DUNGEON_PROGRESS'


def test_a_page_that_could_not_be_read_is_not_an_anchor_miss():
    """MAP with nothing readable is a perception outcome, not a missing button."""
    fields = anchor.classify_refusal('MAP', 'no_candidate_node_observed')
    assert fields['stop_kind'] == anchor.PAGE_UNREADABLE
    assert 'anchor' not in fields


def test_an_evidenced_refusal_stays_held():
    """Refusing to press a forbidden control is a correct outcome, not a defect."""
    fields = anchor.classify_refusal('SHOP_PURCHASE', 'control_is_forbidden')
    assert fields['stop_kind'] == anchor.HELD


def test_recovery_rungs_are_recorded_when_they_were_spent():
    fields = anchor.classify_refusal('MAP', 'enter_button_not_anchored',
                                     tried=('pinch_out', 'drag_down'))
    assert fields['recovery_tried'] == ['pinch_out', 'drag_down']


def test_every_refusal_in_the_window_layer_reaches_this_contract():
    """A new page-specific refusal must be declared, not shipped silently.

    This is the counter-example that keeps the class from growing: adding
    ``_refuse(page, 'some_new_thing_not_anchored')`` passes (it is an anchor
    miss), but adding a *new non-anchor* stop without declaring it here fails.
    """
    undeclared = anchor.undeclared(_refused_reasons())
    assert undeclared == [], (
        f'{len(undeclared)} refusal(s) bypass the anchor contract: {undeclared[:5]}')


def test_the_guard_catches_an_undeclared_refusal():
    """Negative case: the guard above is not vacuous."""
    assert anchor.undeclared(['brand_new_page_specific_stop']) == [
        'brand_new_page_specific_stop']


@pytest.mark.parametrize('page,reason', [
    ('DUNGEON_PROGRESS', 'continue_button_not_anchored'),
    ('MAP', 'no_candidate_node_observed'),
    ('SHOP', 'control_is_forbidden'),
])
def test_the_window_plan_carries_the_kind(page, reason):
    from maalimbus import window
    plan = window._refuse(page, reason)
    assert plan['action'] == window.RECORD
    assert plan['reason'] == reason
    assert plan['stop_kind'] == anchor.stop_kind_of(reason)
