"""Every plan the loop sends must be visible to the reader that gates it.

D57 measured the index's blind spot instead of closing it: two writers named their plan
words in a way no static reader could follow -- a concatenation of a parameter
(`battle_assignment + '_is_the_proven_auto_assign_control'`, 152 recorded sends) and a word
handed over in `initial['reason']` (8 sends).  D64 moved both words into the window layer as
literals, so the declaration is empty; these cases pin the words, the single source, and the
reader's refusal to guess.  A reader that guesses would be worse than a blind one: it would
invent a word the loop never sends and the gate would compare the archive against fiction.
"""
import ast

import pytest

from maalimbus import pages, plan_reasons, window

BOX = [880, 520, 160, 48]


def test_the_starting_gift_row_names_its_own_word():
    plan = window.plan_step('INITIAL_GIFTS', controls={},
                            initial={'point': (100, 120),
                                     'gift': {'row': 2, 'title': 'Bloody Mist'}})
    assert plan['reason'] == 'the_starting_gift_row_is_taken_from_the_tray'
    assert plan['advance'] is True
    # A dismissal proof: the only successor this pick can name is "the page changed".
    assert list(plan['expect']) == ['*']


def test_the_keyword_pick_names_the_fallback_word():
    plan = window.plan_step('INITIAL_GIFTS', controls={},
                            initial={'point': (100, 120), 'keyword': 'Bleed'})
    assert plan['reason'] == 'the_starting_gift_is_picked_from_the_rotation_keyword'


def test_a_reason_handed_over_by_a_caller_cannot_rename_the_plan():
    # The runner used to pass `initial['reason']`; the layer now owns the word, so a
    # caller cannot smuggle in a name the index has never seen.
    plan = window.plan_step('INITIAL_GIFTS', controls={},
                            initial={'point': (100, 120),
                                     'reason': 'a_word_from_somewhere_else',
                                     'gift': {'row': 1, 'title': 'X'}})
    assert plan['reason'] == 'the_starting_gift_row_is_taken_from_the_tray'


def test_both_battle_modes_name_their_own_word():
    win = window.plan_step('BATTLE_HUD', controls={}, battle_assignment='win_rate',
                           auto_assign={'win_rate': BOX}, battle_previous='submit')
    assert win['reason'] == 'win_rate_is_the_proven_auto_assign_control'
    damage = window.plan_step('BATTLE_HUD', controls={}, battle_assignment='damage',
                              auto_assign={'damage': BOX})
    assert damage['reason'] == 'damage_is_the_proven_auto_assign_control'


def test_both_battle_words_are_gated_against_their_successors():
    plans = plan_reasons.acting_plans()
    for word in ('win_rate_is_the_proven_auto_assign_control',
                 'damage_is_the_proven_auto_assign_control'):
        assert plans[word]['expects'] == 5, word
        assert 'BATTLE_PLANNING' in plans[word]['expect_names'], word


def test_the_reader_refuses_to_guess_a_concatenated_reason():
    # The counter-example that keeps the gate honest: a BinOp is not a word, and the
    # reader says so instead of inventing one.
    node = ast.parse("_plan(page, CLICK, reason=battle_assignment + '_x')").body[0].value
    # A BinOp yields no name at all -- which is exactly how the 152-send word stayed
    # invisible: the reader returned nothing and nothing complained.
    assert plan_reasons._elements(node.keywords[0].value) == []


def test_no_acting_plan_is_invisible_to_the_index():
    assert pages.PLANS_THE_INDEX_CANNOT_NAME == {}
    # And nothing the archive saw is missing from the index either (skipped without it).
    from maalimbus import plan_outcomes
    found = plan_outcomes.outcomes()
    if not found:
        pytest.skip('no retained archive')
    plans = plan_reasons.acting_plans()
    assert [word for word in found if word not in plans] == []


def test_the_two_d64_words_are_not_declared_as_dismissal_proofs():
    # They carry named successors, so listing them as "page must change" would be a lie.
    plans = plan_reasons.acting_plans()
    for word in ('win_rate_is_the_proven_auto_assign_control',
                 'damage_is_the_proven_auto_assign_control'):
        assert plans[word]['dismissal'] is False
        assert word not in pages.PLANS_WITH_ONLY_A_DISMISSAL
