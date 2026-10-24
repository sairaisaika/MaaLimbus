"""D106: a drag on the battle board is a game action, not a view move.

The user reproduced the loop dragging a skill slot across the battle screen. The
recovery ladder spends swipes to move a *viewport*; on a board whose controls are fixed
that same swipe grabs a card. So those pages get the settle wait and nothing else.
"""
import pytest

from maalimbus import runner


BATTLE = ('BATTLE_HUD', 'BATTLE_PLANNING', 'BATTLE_TIP', 'BATTLE_RESULT',
          'DEPLOYMENT', 'PRE_BATTLE_TEAM', 'ENCOUNTER', 'REWARD_CARD')


def _loop(tmp_path):
    return runner.MirrorRunner(runner.FakeDevice(), settings={'rounds': 1, 'interval': 0},
                               directory=tmp_path)


@pytest.mark.parametrize('page', BATTLE)
def test_a_fixed_control_page_gets_one_wait_and_no_gesture(tmp_path, page):
    loop = _loop(tmp_path)
    assert loop._ladder_length(page) == 1


@pytest.mark.parametrize('page', ('MAP', 'SHOP', 'GIFT_PICK'))
def test_a_page_with_a_view_to_move_keeps_its_ladder(tmp_path, page):
    loop = _loop(tmp_path)
    assert loop._ladder_length(page) == len(runner.RECOVERY_LADDER)


def test_the_two_fixed_sets_do_not_contradict_each_other():
    assert not set(runner.FIXED_LAYOUT_PAGES) & set(runner.FIXED_CONTROL_PAGES)


def test_the_battle_pages_are_the_ones_with_cards_on_them():
    roster = set(BATTLE) & set(runner.FIXED_CONTROL_PAGES)
    assert roster == set(BATTLE), 'every battle board must be in the fixed-control set'
