"""A map click polls twice, because the third read measured nothing (D122 note)."""
import pytest

from maalimbus import window


def _controls():
    return {'map.card': None}


def _plan(**kwargs):
    base = dict(candidates=[[600, 400, 40, 40]], candidate_index=0)
    base.update(kwargs)
    return window.plan_step('MAP', controls={'map.progress_button': None}, **base)


def test_a_map_click_polls_twice_and_not_six_times():
    plan = _plan()
    assert plan['reason'] == 'map_node_click_is_the_only_proven_forward_input'
    assert plan['settle_rounds'] == 2


def test_the_rounds_are_a_floor_not_a_ceiling():
    # The runner clamps the page budget down to this value; it can never raise it.
    plan = _plan()
    assert 1 <= plan['settle_rounds'] <= 2


def test_another_page_keeps_its_own_answer():
    plan = window.plan_step('REVIVE_PICK', controls={})
    assert plan.get('settle_rounds') is None
