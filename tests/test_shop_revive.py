"""The shop's Heal Sinner service and the key-slot rule that asks for it.

The label evidence is the retained live shop frame
``window-20261012-210547/frame-0005.json`` (panel x 180-660, y 540-800), whose own OCR
reads ``Heal`` at [298,688,...] and ``Sinner`` at [286,704,...] with the cost badge
``100`` at [264,742,62,30]; the frames are git-ignored, so the tokens are rebuilt here as
the reader's contract rather than cited as a fixture path.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from maalimbus.shop_revive import (KEY_POSITIONS, heal_sinner, heal_sinners_options,
                                   key_losses, modal_bottom_control, picker_slot,
                                   saved_order, slot_box, unavailable_sinners)
from maalimbus.vision import Text


def row(text, box, score=.99):
    return Text(text, tuple(box), score)


def panel(heal=(298, 688, 60, 26), sinner=(286, 704, 72, 30), cost=(264, 742, 62, 30),
          cost_text='100'):
    rows = [row('Enhance', (222, 565, 90, 30)), row('Gifts', (238, 585, 70, 24)),
            row('Heal', heal), row('Sinner', sinner)]
    if cost is not None:
        rows.append(row(cost_text, cost))
    return rows


def test_the_panels_own_two_labels_and_their_badge_are_the_button():
    service = heal_sinner(panel())
    assert service is not None
    assert service.label == 'Heal Sinner'
    assert service.box == (286, 688, 72, 46)
    assert service.cost == 100
    assert service.cost_box == (264, 742, 62, 30)


def test_a_badge_that_is_not_printed_leaves_the_cost_unknown_but_keeps_the_button():
    service = heal_sinner(panel(cost=None))
    assert service is not None and service.cost is None and service.cost_box is None


def test_a_faint_or_repeated_or_misplaced_label_is_never_a_service():
    assert heal_sinner(panel(heal=(298, 688, 60, 26), sinner=(286, 704, 72, 30))
                       + [row('Sinner', (286, 704, 72, 30), .99)]) is None
    faint = [row('Heal', (298, 688, 60, 26), .5), row('Sinner', (286, 704, 72, 30), .99)]
    assert heal_sinner(faint) is None
    outside = [row('Heal', (298, 200, 60, 26)), row('Sinner', (286, 216, 72, 30))]
    assert heal_sinner(outside) is None
    assert heal_sinner([row('Team', (528, 696, 60, 26)), row('Sinner', (286, 704, 72, 30))]) is None


def test_a_single_digit_badge_is_not_a_price_under_the_button():
    service = heal_sinner(panel(cost_text='7'))
    assert service is not None and service.cost is None and service.cost_box is None


def options_panel(first='I. Greatly heal a single Sinner.'):
    """The Heal Sinners modal of window-20261012-212047/frame-0012.json, as its OCR read it."""
    return [row('Heal Sinners', (212, 55, 256, 42), 1),
            row(first, (1256, 246, 380, 33), .968),
            row('100', (1764, 246, 52, 39), 1),
            row('2. Moderately heal every Sinner.', (1246, 432, 332, 28), .991),
            row('100', (1764, 428, 54, 42), 1),
            row('3. Revive a single Sinner.', (1246, 611, 326, 34), .991),
            row('100', (1768, 611, 50, 42), 1),
            row('Return', (1610, 941, 172, 55), 1)]


def test_the_modals_three_numbered_options_are_read_and_the_third_is_the_revive():
    options = heal_sinners_options(options_panel())
    assert options is not None
    assert options.rows == ((1256, 246, 380, 33), (1246, 432, 332, 28),
                            (1246, 611, 326, 34))
    assert options.costs == (100, 100, 100)
    assert options.revive_box == (1246, 611, 326, 34)


def test_the_first_ordinal_may_be_read_as_a_letter_or_a_digit():
    # The live frame reads the first option's '1.' as 'I.'; the rows are taken in reading
    # order, so the third one is the revive either way.
    for first in ('I. Greatly heal a single Sinner.', '1. Greatly heal a single Sinner.',
                  'l. Greatly heal a single Sinner.'):
        options = heal_sinners_options(options_panel(first))
        assert options is not None and options.revive_box == (1246, 611, 326, 34)


def test_the_modals_options_are_only_read_when_all_three_print_their_own_cost():
    assert heal_sinners_options([r for r in options_panel()
                                 if r.text != '3. Revive a single Sinner.']) is None
    assert heal_sinners_options([r for r in options_panel()
                                 if r.text != '100']) is None
    repeated = options_panel() + [row('3. Revive a single Sinner.', (1246, 611, 326, 34))]
    assert heal_sinners_options(repeated) is None
    assert heal_sinners_options([row('1. Heal', (100, 100, 100, 20)),
                                 row('2. Heal', (100, 200, 100, 20)),
                                 row('3. Heal', (100, 300, 100, 20))]) is None


def test_the_deployment_stores_own_exclusions_are_the_dead_list():
    store = dict(scope='run', saved_order=[6, 2, 4, 9, 12, 7, 11, 10, 3, 1, 8, 5],
                 order=[2, 4, 9, 12, 7, 11, 10, 3, 1, 8, 5], unavailable=[6],
                 rejected_unavailable_inputs=[
                     dict(intent=dict(kind='card', card=9),
                          proof=dict(unavailable=[9, 6], accepted=True))])
    assert unavailable_sinners(store) == [6, 9]
    assert unavailable_sinners({}) == []
    # A revive the shop's own counter proved takes the card back off the dead list, so the
    # service is never bought for the same Sinner twice in one run.
    store['revives'] = [dict(card=6, cost=100, coins_before=3093, coins_after=2993)]
    assert unavailable_sinners(store) == [9]
    assert saved_order(store) == [6, 2, 4, 9, 12, 7, 11, 10, 3, 1, 8, 5]
    # Only the slots the operator called key come back, and a card the order does not
    # hold at all is never one of them.
    assert key_losses([6], saved_order(store)) == [6]
    assert key_losses([6], saved_order(store), positions=0) == []
    assert key_losses([10, 2], saved_order(store)) == [2]
    assert key_losses([6], []) == []
    assert KEY_POSITIONS == 7


def test_the_pickers_bar_slot_is_the_deck_card_the_proof_names():
    # The picker's own bar (evidence/runtime/window-20261012-213008/frame-0002.png): twelve
    # hexagonal portraits at a 115 px pitch from the first slot's centre at x 112, the
    # second slot's own '252' at [222,996,38,26] and the twelfth's '185' at [1378,996,...].
    assert slot_box(1) == [67, 880, 90, 120]
    assert slot_box(2) == [182, 880, 90, 120]
    assert slot_box(6) == [642, 880, 90, 120]
    assert slot_box(12) == [1332, 880, 90, 120]
    # A deck slot that does not exist has no box, and the scale is read off the frame.
    assert slot_box(0) is None and slot_box(13) is None and slot_box('6') is None
    assert slot_box(1, (960, 540)) == [33, 440, 45, 60]


def test_the_picker_slot_is_the_first_dead_key_slot_or_nothing():
    store = dict(saved_order=[6, 2, 4, 9, 12, 7, 11, 10, 3, 1, 8, 5], unavailable=[6])
    assert picker_slot(unavailable_sinners(store), saved_order(store)) == slot_box(6)
    # A death outside the first seven saved slots is not one the operator's rule brings
    # back, and a run with no proof at all has nothing to aim at.
    outer = dict(saved_order=[2, 4, 9, 12, 7, 11, 10, 3, 1, 8, 5, 6], unavailable=[6])
    assert picker_slot(unavailable_sinners(outer), saved_order(outer)) is None
    assert picker_slot([], saved_order(store)) is None
    assert picker_slot([6], []) is None


def test_the_modals_own_bottom_button_is_read_from_the_word_it_prints():
    # One band carries the three-way step's Return [1610,941,172,55], the pick step's
    # Select [1614,937,166,61] and the revived step's Leave [1622,943,150,53] (live
    # window-20261012-213008/frame-0002.json, window-20261012-214635/frame-0006.json and
    # window-20261012-214803/frame-0001.json), so the word is what a step is answered with.
    pick = [row('Select', (1614, 937, 166, 61), 1.0), row('Heal again.', (1242, 456, 146, 34), 1.0)]
    assert modal_bottom_control(pick, [r'^Select$']) == [1614, 937, 166, 61]
    # The option rows above the button are drawn in every state and are never the target.
    assert modal_bottom_control(pick, [r'^Leave$']) is None
    done = [row('Hong Lu, revived, returns to battle.', (108, 573, 416, 28), .98),
            row('Leave', (1622, 943, 150, 53), 1.0)]
    assert modal_bottom_control(done, [r'^Leave$']) == [1622, 943, 150, 53]
    # A word outside the band, a faint one, or two of them is no target at all.
    assert modal_bottom_control([row('Leave', (1400, 943, 150, 53), 1.0)], [r'^Leave$']) is None
    assert modal_bottom_control([row('Leave', (1622, 943, 150, 53), .5)], [r'^Leave$']) is None
    assert modal_bottom_control(done + [row('Leave', (1700, 960, 60, 30), 1.0)],
                                [r'^Leave$']) is None
    assert modal_bottom_control([], [r'^Leave$']) is None
