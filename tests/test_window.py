"""Tests for the bounded window step planner.

The planner decides which single input a live page may receive; every case here
is a page that the live tools have already met, plus the refusals that keep an
unproven page from receiving a guessed coordinate.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.vision import Text, classify  # noqa: E402
from maalimbus.window import (ANY, CLICK, NODE, RECORD, SWIPE, plan_step,
                              resolve_overlay,
                              step_result, successor_ok)  # noqa: E402

CONTROLS = {'node_panel.enter_button': [1668, 780, 124, 63],
            'pre_battle.battle_button': [1674, 859, 144, 44],
            'entry.enter_button': [1534, 716, 96, 36],
            'home.drive_button': [1438, 968, 68, 28]}
CONTROLS.update({'pre_battle.card_%02d' % index:
                 [355 + 195 * ((index - 1) % 6), 236 + 296 * ((index - 1) // 6), 190, 248]
                 for index in range(1, 13)})


def test_map_clicks_the_planned_candidate_and_expects_the_panel():
    plan = plan_step('MAP', candidates=[[900, 400, 60, 60], [1200, 500, 60, 60]])
    assert plan['action'] == CLICK
    assert plan['target'] == [900, 400, 60, 60]
    assert plan['expect'][0] == 'NODE_PANEL'
    assert successor_ok(plan, 'NODE_PANEL')
    # Live proof: build/window-run73.json step17 clicked a node and landed on
    # PRE_BATTLE_TEAM, which the panel-only expectation read as an unexpected successor.
    assert successor_ok(plan, 'PRE_BATTLE_TEAM')
    assert not successor_ok(plan, 'MAP')


def test_map_without_a_candidate_refuses_instead_of_guessing():
    plan = plan_step('MAP', candidates=[])
    assert plan['action'] == RECORD
    assert plan['reason'] == 'no_candidate_node_observed'
    assert plan['target'] is None


def test_map_candidate_index_must_be_in_range():
    plan = plan_step('MAP', candidates=[[900, 400, 60, 60]], candidate_index=3)
    assert plan['action'] == RECORD
    assert plan['reason'] == 'candidate_index_out_of_range'


def test_home_uses_the_drive_nav_box_and_accepts_the_drive_page():
    plan = plan_step('HOME', controls=CONTROLS)
    assert plan['action'] == CLICK
    assert plan['target'] == CONTROLS['home.drive_button']
    assert 'DRIVE' in plan['expect']
    assert successor_ok(plan, 'DRIVE')


def test_home_without_the_anchor_refuses():
    plan = plan_step('HOME', controls={})
    assert plan['action'] == RECORD
    assert plan['reason'] == 'drive_button_not_anchored'


def test_drive_delegates_to_the_proven_pipeline_node():
    plan = plan_step('DRIVE')
    assert plan['action'] == NODE
    assert plan['node'] == 'WindowDrive'
    assert successor_ok(plan, 'MIRROR_ENTRY')
    assert not successor_ok(plan, 'SHOP')


def test_node_panel_uses_the_anchored_enter_button():
    plan = plan_step('NODE_PANEL', controls=CONTROLS)
    assert plan['action'] == CLICK
    assert plan['target'] == CONTROLS['node_panel.enter_button']
    assert plan['expect'][:4] == ['PRE_BATTLE_TEAM', 'SHOP', 'MAP', 'CUTSCENE']
    assert 'UNKNOWN' in plan['expect']


def test_node_panel_without_the_anchor_refuses():
    plan = plan_step('NODE_PANEL', controls={})
    assert plan['action'] == RECORD
    assert plan['reason'] == 'enter_button_not_anchored'


def test_pre_battle_team_uses_the_anchored_battle_button():
    plan = plan_step('PRE_BATTLE_TEAM', controls=CONTROLS)
    assert plan['target'] == CONTROLS['pre_battle.battle_button']
    assert 'BATTLE_HUD' in plan['expect']


def test_pre_battle_team_joins_the_next_unpicked_card_before_battling():
    # Live proof: evidence/runtime/window-20261006-030750/frame-0001.json opens at
    # 0/12 with a dark Battle! button; picking eleven more cards reaches 12/12 and
    # only then does the button light up. Never click a card that already has a badge
    # (that would take its identity back out of the team).
    states = [None] * 12
    plan = plan_step('PRE_BATTLE_TEAM', controls=CONTROLS, team={'states': states})
    assert plan['target'] == CONTROLS['pre_battle.card_01']
    assert plan['reason'] == 'team_card_joins_the_next_unpicked_identity'
    assert plan['advance'] is True
    assert plan['detail'] == {'card_index': 1}
    # A click on a card only changes pixels, so it is proven by the frame moving.
    assert successor_ok(plan, 'PRE_BATTLE_TEAM') is False
    assert step_result(plan, sent=True, before='PRE_BATTLE_TEAM',
                       after='PRE_BATTLE_TEAM', page='PRE_BATTLE_TEAM',
                       frame_changed=True)['passed'] is True
    assert step_result(plan, sent=True, before='PRE_BATTLE_TEAM',
                       after='PRE_BATTLE_TEAM', page='PRE_BATTLE_TEAM',
                       frame_changed=False)['passed'] is False
    # Skipping the picked cards and stopping at the first gap keeps the order stable.
    states = ['selected'] * 6 + ['backup'] + [None] * 5
    plan = plan_step('PRE_BATTLE_TEAM', controls=CONTROLS, team={'states': states})
    assert plan['target'] == CONTROLS['pre_battle.card_08']
    assert plan['detail'] == {'card_index': 8}


def test_pre_battle_team_battles_once_every_card_is_in_the_team():
    plan = plan_step('PRE_BATTLE_TEAM', controls=CONTROLS,
                     team={'states': ['selected'] * 7 + ['backup'] * 5})
    assert plan['target'] == CONTROLS['pre_battle.battle_button']
    assert plan['reason'] == 'battle_button_submits_the_team'


def test_battle_prefers_start_and_falls_back_to_win_rate():
    start = plan_step('BATTLE_HUD', start_box=[1038, 771, 121, 133],
                      auto_assign={'win_rate': [1198, 796, 48, 41]})
    assert start['target'] == [1038, 771, 121, 133]
    assert start['reason'] == 'start_button_submits_the_assigned_turn'
    win = plan_step('BATTLE_HUD', start_box=None,
                    auto_assign={'win_rate': [1198, 796, 48, 41]})
    assert win['target'] == [1198, 796, 48, 41]
    assert win['reason'] == 'win_rate_is_the_proven_auto_assign_control'


def test_the_battle_planning_sub_state_takes_the_same_inputs():
    """Live window-20261006-053000-frame-0031 named the battle screen BATTLE_PLANNING.

    The WAVE/TURN captions are not read on that frame, so agent/recognition.py calls
    it the planning sub-state; the forward input is still assign-then-submit, and the
    other sub-state must be an accepted successor instead of stopping the run.
    """
    assign = plan_step('BATTLE_PLANNING', start_box=None,
                       auto_assign={'win_rate': [1198, 796, 48, 41]})
    assert assign['action'] == CLICK
    assert assign['target'] == [1198, 796, 48, 41]
    assert successor_ok(assign, 'BATTLE_HUD')
    assert successor_ok(assign, 'BATTLE_PLANNING')
    start = plan_step('BATTLE_PLANNING', start_box=[1038, 771, 121, 133], auto_assign=None)
    assert start['reason'] == 'start_button_submits_the_assigned_turn'
    assert successor_ok(start, 'BATTLE_PLANNING')
    refused = plan_step('BATTLE_PLANNING', start_box=None, auto_assign=None)
    assert refused['reason'] == 'battle_has_no_proven_control'


def test_battle_without_a_proven_control_refuses():
    plan = plan_step('BATTLE_HUD', start_box=None, auto_assign=None)
    assert plan['action'] == RECORD
    assert plan['reason'] == 'battle_has_no_proven_control'


def test_unproven_pages_are_observe_only():
    for page in ('EVENT_DIALOG', 'REWARD_SETTLE', 'FLOOR_GIFTS', 'UNKNOWN'):
        plan = plan_step(page, controls=CONTROLS,
                         start_box=[1, 2, 3, 4], candidates=[[5, 6, 7, 8]])
        assert plan['action'] == RECORD, page
        assert plan['reason'] == 'page_is_observe_only'
        assert plan['target'] is None


def test_the_victory_screen_names_the_anchor_it_is_missing():
    plan = plan_step('BATTLE_RESULT', controls=CONTROLS, start_box=[1, 2, 3, 4])
    assert plan['action'] == RECORD
    assert plan['reason'] == 'battle_result_control_not_anchored'
    assert plan['target'] is None


def test_the_entry_page_has_one_plan_under_both_spellings():
    def body(plan):
        return {key: value for key, value in plan.items() if key != 'page'}

    controls = dict(CONTROLS, **{'entry.enter_button': [11, 22, 33, 44]})
    assert body(plan_step('BEFORE_ENTRY', controls=controls)) == \
        body(plan_step('MIRROR_ENTRY', controls=controls))
    without = plan_step('BEFORE_ENTRY', controls=CONTROLS)
    assert body(without) == body(plan_step('MIRROR_ENTRY', controls=CONTROLS))
    assert without['reason'] != 'page_is_observe_only'


def test_successor_outside_the_expected_set_is_recorded_as_a_failure():
    # The map accepts anything a node can hand back, so the outsider here has to be a page
    # a node click can never reach - the battle HUD needs a fight to have started.
    plan = plan_step('MAP', candidates=[[900, 400, 60, 60]])
    assert not successor_ok(plan, 'BATTLE_HUD')
    record = step_result(plan, sent=True, before='MAP', after='BATTLE_HUD',
                         page='BATTLE_HUD')
    assert record['passed'] is False
    assert record['reason'] == 'unexpected_successor'
    assert record['clicks_sent'] == 1


def test_refusal_records_no_click():
    plan = plan_step('BATTLE_HUD', start_box=None, auto_assign=None)
    record = step_result(plan, sent=False, before='BATTLE_HUD', after=None,
                         page='BATTLE_HUD')
    assert record['passed'] is False
    assert record['clicks_sent'] == 0
    assert record['page_after'] == 'BATTLE_HUD'


def test_tutorial_overlay_advances_before_entry_is_live():
    # Live proof: evidence/runtime/window-20261006-023714/frame-0001.json is a
    # tutorial overlay whose underlying Enter is inert (a click left the frame
    # byte-identical), so the overlay's own continue control is the only input.
    plan = plan_step('TUTORIAL', controls={'tutorial.next_button': [1782, 505, 76, 52]})
    assert plan['action'] == CLICK
    assert plan['target'] == [1782, 505, 76, 52]
    assert plan['expect'] == [ANY]
    assert plan['advance'] is True
    # The overlay's cards uncover many different pages, so the only decidable
    # failure is that the overlay is still there after the click.
    assert successor_ok(plan, 'MIRROR_ENTRY')
    assert successor_ok(plan, 'DUNGEON_TEAM')
    assert successor_ok(plan, 'UNKNOWN')
    assert not successor_ok(plan, 'TUTORIAL')
    # Card after card keeps the same page label, so the changed frame is the
    # proof that the click landed (live: window-20261006-030013 frame-0001 vs
    # frame-0002 are two different "Creating your Team" cards).
    stuck = step_result(plan, sent=True, before='TUTORIAL', after='TUTORIAL',
                        page='TUTORIAL', frame_changed=False)
    assert stuck['passed'] is False and stuck['reason'] == 'unexpected_successor'
    advanced = step_result(plan, sent=True, before='TUTORIAL', after='TUTORIAL',
                           page='TUTORIAL', frame_changed=True)
    assert advanced['passed'] is True
    assert plan['reason'] == 'tutorial_overlay_must_be_dismissed_before_enter_is_live'
    unanchored = plan_step('TUTORIAL', controls={})
    assert unanchored['action'] == RECORD
    assert unanchored['reason'] == 'tutorial_next_button_not_anchored'


def test_tutorial_follows_the_live_page_turn_triangle():
    # Live proof: the book's last page keeps only the left triangle
    # (evidence/runtime/window-20261006-030152/frame-0014.png, previous
    # 93,519,40,44, next absent), so a fixed right-edge box clicks empty space.
    turned = plan_step('TUTORIAL', controls={'tutorial.next_button': [1782, 505, 76, 52]},
                       arrows={'previous': [93, 519, 40, 44], 'next': [1787, 517, 40, 44]})
    assert turned['action'] == CLICK
    assert turned['target'] == [1787, 517, 40, 44]
    last = plan_step('TUTORIAL', controls={'tutorial.next_button': [1782, 505, 76, 52]},
                     arrows={'previous': [93, 519, 40, 44], 'next': None})
    assert last['action'] == RECORD
    assert last['reason'] == 'tutorial_last_page_has_no_forward_control'
    # With the book's own header arrow anchored it outranks ▶: the header closes the
    # whole guide, while ▶ only turns one page (live: build/window-run50.json turned
    # eleven pages without ever reaching the team page underneath; the player read
    # that screen and said to click the top-left corner instead).
    closed = plan_step('TUTORIAL',
                       controls={'tutorial.next_button': [1782, 505, 76, 52],
                                 'tutorial.book_close': [83, 27, 114, 77]},
                       arrows={'previous': [93, 519, 40, 44], 'next': None})
    assert closed['action'] == CLICK
    assert closed['target'] == [83, 27, 114, 77]
    assert closed['advance'] is True
    assert closed['reason'] == 'tutorial_book_is_closed_from_its_own_header_arrow'
    assert successor_ok(closed, 'PRE_BATTLE_TEAM')
    assert not successor_ok(closed, 'TUTORIAL')
    opening = plan_step('TUTORIAL',
                        controls={'tutorial.next_button': [1782, 505, 76, 52],
                                  'tutorial.book_close': [83, 27, 114, 77]},
                        arrows={'previous': [93, 519, 40, 44], 'next': [1787, 517, 40, 44]})
    assert opening['target'] == [83, 27, 114, 77]
    # Without a frame reading at all the anchor is still the best available box.
    blind = plan_step('TUTORIAL', controls={'tutorial.next_button': [1787, 517, 39, 44]})
    assert blind['target'] == [1787, 517, 39, 44]


def test_tutorial_overlay_outranks_the_page_it_covers():
    # Live proof: card 2 of the overlay (evidence/runtime/window-20261006-024050/
    # frame-0002.json) is not in the OCR token, so the covered entry page would be
    # planned and its inert Enter would swallow the step. The continue control is
    # the overlay's stable identity, so it outranks the label underneath.
    assert resolve_overlay('MIRROR_ENTRY', overlay_hit=True) == 'TUTORIAL'
    assert resolve_overlay('TUTORIAL', overlay_hit=True) == 'TUTORIAL'
    assert resolve_overlay('MIRROR_ENTRY', overlay_hit=False) == 'MIRROR_ENTRY'
    assert resolve_overlay('MAP', overlay_hit=None) == 'MAP'


def test_the_guide_book_may_cover_the_page_after_any_input():
    # Live proof: build/window-run3.json step 1 clicked "To Battle!" on the pre
    # battle team page (target 1674,859,144,44) and the guide book came up over the
    # battle HUD, so a step that only expected BATTLE_HUD reported
    # unexpected_successor and stopped the run.
    plan = plan_step('PRE_BATTLE_TEAM', controls=CONTROLS)
    assert plan['action'] == CLICK
    assert successor_ok(plan, 'TUTORIAL')
    # The overlay's own plan is unaffected: it still has to be gone afterwards.
    overlay = plan_step('TUTORIAL', controls={'tutorial.next_button': [1782, 505, 76, 52]})
    assert not successor_ok(overlay, 'TUTORIAL')
    assert successor_ok(overlay, 'BATTLE_HUD')


def test_resume_dialog_resumes_and_never_halts_the_run():
    # Live proof: evidence/runtime/window-20261006-025617/frame-0002.json is the
    # "Dungeon Progress" prompt of a run that a second Enter press re-opens.
    resume = [902, 579, 114, 34]
    plan = plan_step('RESUME_DIALOG', controls={'resume.resume_button': resume})
    assert plan['action'] == CLICK
    assert plan['target'] == resume
    assert plan['reason'] == 'resume_rejoins_the_run_that_is_already_in_progress'
    assert successor_ok(plan, 'MAP') and not successor_ok(plan, 'SHOP')
    missing = plan_step('RESUME_DIALOG', controls={})
    assert missing['action'] == RECORD
    assert missing['reason'] == 'resume_button_not_anchored'
    # The page carries Halt Exploration, and no plan may ever land on it: not by
    # naming it as the control to click, and not by a mis-registered resume anchor.
    halt = [848, 647, 222, 33]
    named = plan_step('RESUME_DIALOG', controls={'resume.halt_button': halt})
    assert named['action'] == RECORD
    misregistered = plan_step('RESUME_DIALOG',
                              controls={'resume.resume_button': halt,
                                        'resume.halt_button': halt})
    assert misregistered['action'] == RECORD
    assert misregistered['reason'] == 'control_is_forbidden'


def test_the_graces_page_buys_what_is_affordable_then_leaves_by_its_own_enter():
    # Live: evidence/runtime/window-20261006-193843/frame-0004.json reads the page
    # title at the top left and its own Enter at [1740,986,102,42]; the + button of
    # card 1 sits at (271,534).
    enter = [1740, 986, 102, 42]
    buy = plan_step('STAR_GRACES', controls={'graces.enter_button': enter},
                    graces={'card': 1, 'point': (271, 534)})
    assert buy['action'] == CLICK
    assert buy['target'] == [226, 511, 90, 46]
    assert buy['advance'] is True
    assert buy['reason'] == 'grace_card_is_bought_within_the_available_starlight'
    assert buy['detail'] == {'card': 1}
    leave = plan_step('STAR_GRACES', controls={'graces.enter_button': enter})
    assert leave['target'] == enter
    assert leave['reason'] == 'the_graces_page_is_left_with_its_own_enter'
    assert successor_ok(leave, 'INITIAL_GIFTS') and successor_ok(leave, 'MAP')
    assert not successor_ok(leave, 'STAR_GRACES')
    # A grace the driver could not locate must not turn into a blind click.
    assert plan_step('STAR_GRACES', controls={})['reason'] == 'graces_enter_not_anchored'
    # A located grace is still bought even when the page anchor is missing.
    assert plan_step('STAR_GRACES', controls={},
                     graces={'card': 2, 'point': (518, 534)})['target'] == [473, 511, 90, 46]


def test_the_gift_pickup_popup_is_acknowledged_with_its_confirm():
    # Live: evidence/runtime/window-20261006-201456/frame-0001.json, the modal the run
    # raises over the map after picking a gift up.
    confirm = [916, 825, 126, 40]
    plan = plan_step('EGO_GIFT_POPUP', controls={'ego_gift_popup.confirm_button': confirm})
    assert plan['action'] == CLICK
    assert plan['target'] == confirm
    assert plan['reason'] == 'the_ego_gift_popup_is_acknowledged_with_its_confirm'
    assert successor_ok(plan, 'MAP') and not successor_ok(plan, 'EGO_GIFT_POPUP')
    assert plan_step('EGO_GIFT_POPUP', controls={})['reason'] == \
        'ego_gift_popup_confirm_not_anchored'


def test_the_battle_result_is_waited_out_rather_than_stopped_on():
    # Live: build/window-run62.json stopped on BATTLE_RESULT with nothing sent, and the
    # next observation already showed the post-battle story and then the map.
    from maalimbus.window import WAIT_PAGES
    assert WAIT_PAGES == ('UNKNOWN', 'BATTLE_RESULT')
    assert 'MAP' not in WAIT_PAGES and 'PRE_BATTLE_TEAM' not in WAIT_PAGES


def test_the_forgone_gift_search_is_confirmed_and_never_cancelled():
    # Live: evidence/runtime/window-20261006-200357/frame-0001.json is the prompt the
    # refused search raises.
    confirm = [1116, 722, 112, 38]
    cancel = [700, 720, 142, 40]
    plan = plan_step('GIFT_SEARCH_FORGO',
                     controls={'gift_search_forgo.confirm_button': confirm,
                               'gift_search_forgo.cancel_button': cancel})
    assert plan['action'] == CLICK
    assert plan['target'] == confirm
    assert plan['reason'] == 'the_forgone_gift_search_is_confirmed'
    assert successor_ok(plan, 'MAP') and not successor_ok(plan, 'GIFT_SEARCH_FORGO')
    assert plan_step('GIFT_SEARCH_FORGO', controls={})['reason'] == \
        'gift_search_forgo_confirm_not_anchored'
    stolen = plan_step('GIFT_SEARCH_FORGO',
                       controls={'gift_search_forgo.confirm_button': cancel,
                                 'gift_search_forgo.cancel_button': cancel})
    assert stolen['reason'] == 'control_is_forbidden'


def test_the_gift_search_is_refused_and_the_select_path_still_exists():
    # Live: evidence/runtime/window-20261006-195803/frame-0001.json. The tray header
    # prints the running starlight price, so the player asked for the optional search
    # to be refused outright; 'select' stays available as the other mode.
    select = [1568, 845, 88, 30]
    refuse = [1302, 843, 152, 34]
    plan = plan_step('GIFT_SEARCH', controls={'gift_search.select_button': select,
                                              'gift_search.refuse_button': refuse})
    assert plan['action'] == CLICK
    assert plan['target'] == refuse
    assert plan['reason'] == 'the_player_asked_the_optional_gift_search_to_be_refused'
    assert successor_ok(plan, 'MAP') and not successor_ok(plan, 'GIFT_SEARCH')
    other = plan_step('GIFT_SEARCH', controls={'gift_search.select_button': select,
                                               'gift_search.refuse_button': refuse},
                      search={'mode': 'select'})
    assert other['target'] == select
    assert other['reason'] == 'the_gift_search_is_left_without_spending_starlight'
    assert plan_step('GIFT_SEARCH', controls={})['reason'] == \
        'gift_search_refuse_not_anchored'
    assert plan_step('GIFT_SEARCH', controls={},
                     search={'mode': 'select'})['reason'] == \
        'gift_search_select_not_anchored'


def test_the_starting_gift_comes_from_the_rotation_keyword_then_select():
    # Live: evidence/runtime/window-20261006-194741/frame-0001.json reads the tray
    # title, the Bleed column and Select [1524,859,110,42] with its '0/1' counter.
    select = [1524, 859, 110, 42]
    take = plan_step('INITIAL_GIFTS', controls={'initial_gifts.select_button': select},
                     initial={'point': (503, 360), 'keyword': 'bleed',
                              'chosen': 0, 'required': 1})
    assert take['action'] == CLICK
    assert take['target'] == [473, 330, 60, 60]
    assert take['advance'] is True
    assert take['reason'] == 'the_starting_gift_is_picked_from_the_rotation_keyword'
    assert take['detail'] == {'keyword': 'bleed', 'gift': None}
    # The second click takes the tray row the rotation names; the third leaves.
    named = plan_step('INITIAL_GIFTS', controls={'initial_gifts.select_button': select},
                      initial={'point': (1386, 350), 'gift': True,
                               'reason': 'the_starting_gift_row_is_taken_from_the_tray',
                               'chosen': 0, 'required': 1})
    assert named['advance'] is True
    assert named['reason'] == 'the_starting_gift_row_is_taken_from_the_tray'
    assert named['detail'] == {'keyword': None, 'gift': True}
    leave = plan_step('INITIAL_GIFTS', controls={'initial_gifts.select_button': select},
                      initial={'point': None, 'keyword': 'bleed'})
    assert leave['target'] == select
    assert leave['reason'] == 'select_takes_the_starting_gift'
    assert successor_ok(leave, 'MAP') and successor_ok(leave, 'THEME_PACKS')
    # A keyword the frame does not show must never become a blind click.
    assert plan_step('INITIAL_GIFTS', controls={})['reason'] == \
        'initial_gift_select_not_anchored'
    # Refuse Gift abandons the starting gift, so it is never a target.
    refused = [1256, 865, 150, 28]
    stolen = plan_step('INITIAL_GIFTS',
                       controls={'initial_gifts.select_button': refused,
                                 'initial_gifts.refuse_button': refused})
    assert stolen['reason'] == 'control_is_forbidden'


def test_the_grace_selection_prompt_confirms_and_never_cancels():
    # Live: evidence/runtime/window-20261006-194533/frame-0001.json is the prompt the
    # Graces page hands off to.
    confirm = [1040, 778, 148, 35]
    cancel = [740, 774, 148, 41]
    plan = plan_step('STAR_CONFIRM', controls={'star_confirm.confirm_button': confirm,
                                               'star_confirm.cancel_button': cancel})
    assert plan['action'] == CLICK
    assert plan['target'] == confirm
    assert plan['reason'] == 'the_grace_selection_is_confirmed_before_the_run_starts'
    assert successor_ok(plan, 'INITIAL_GIFTS') and successor_ok(plan, 'MAP')
    assert not successor_ok(plan, 'STAR_CONFIRM')
    # Cancel is the way back to the Graces page: it is never a target.
    assert plan_step('STAR_CONFIRM',
                     controls={'star_confirm.cancel_button': cancel})['reason'] == \
        'star_confirm_button_not_anchored'
    # The driver always hands over every anchor of the page, so a mis-registered
    # confirm box that coincides with Cancel is refused.
    stolen = plan_step('STAR_CONFIRM', controls={'star_confirm.confirm_button': cancel,
                                                 'star_confirm.cancel_button': cancel})
    assert stolen['reason'] == 'control_is_forbidden'


def test_the_level_warning_proceeds_and_never_cancels():
    # Live proof: evidence/runtime/window-20261006-193730/frame-0003.json is the
    # prompt the rotation team raises (avg level 55 against a recommended 60).
    dialog_confirm = [1116, 720, 112, 40]
    cancel = [744, 728, 96, 30]
    plan = plan_step('LEVEL_WARNING', controls={'level_warning.confirm_button': dialog_confirm,
                                                'level_warning.cancel_button': cancel})
    assert plan['action'] == CLICK
    assert plan['target'] == dialog_confirm
    assert plan['reason'] == 'the_level_warning_proceeds_with_the_rotation_team'
    assert successor_ok(plan, 'THEME_PACKS') and successor_ok(plan, 'MAP')
    assert not successor_ok(plan, 'LEVEL_WARNING')
    missing = plan_step('LEVEL_WARNING', controls={})
    assert missing['action'] == RECORD
    assert missing['reason'] == 'level_warning_confirm_not_anchored'
    # Cancel backs out of a run the rotation asked for, so it is never a target -
    # not by naming it, and not through a mis-registered anchor.
    named = plan_step('LEVEL_WARNING', controls={'level_warning.cancel_button': cancel})
    assert named['action'] == RECORD
    misregistered = plan_step('LEVEL_WARNING',
                              controls={'level_warning.confirm_button': cancel,
                                        'level_warning.cancel_button': cancel})
    assert misregistered['action'] == RECORD
    assert misregistered['reason'] == 'control_is_forbidden'


def test_the_dungeon_team_page_brings_the_rotation_slot_then_confirms():
    # Live proof: evidence/runtime/window-20261006-193439/frame-0002.json is the
    # loadout picker a run opens on - TEAMS #1..#7 down the left edge, Starlight
    # Bonus 107 and Confirm on the bottom right.
    slot5 = [152, 673, 88, 21]
    confirm = [1632, 853, 170, 52]
    controls = {'team.slot_05': slot5, 'team.confirm_button': confirm}
    picked = plan_step('DUNGEON_TEAM', controls=controls,
                       team={'wanted': 5, 'selected': 1})
    assert picked['action'] == CLICK
    assert picked['target'] == slot5
    assert picked['advance'] is True
    assert picked['detail'] == {'slot': 5}
    assert picked['reason'] == 'dungeon_team_slot_is_selected_for_the_rotation'
    entered = plan_step('DUNGEON_TEAM', controls=controls,
                        team={'wanted': 5, 'selected': 5})
    assert entered['action'] == CLICK
    assert entered['target'] == confirm
    assert entered['reason'] == 'dungeon_team_confirm_brings_the_chosen_team_in'
    assert successor_ok(entered, 'MAP') and successor_ok(entered, 'UNKNOWN')
    assert not successor_ok(entered, 'DUNGEON_TEAM')
    # Without a rotation the page must still be able to start the run.
    blind = plan_step('DUNGEON_TEAM', controls=controls,
                      team={'wanted': None, 'selected': None})
    assert blind['target'] == confirm
    missing = plan_step('DUNGEON_TEAM', controls={'team.slot_05': slot5},
                        team={'wanted': 5, 'selected': 5})
    assert missing['action'] == RECORD
    assert missing['reason'] == 'dungeon_team_confirm_not_anchored'


def test_the_entry_confirmation_starts_the_run_and_cancel_is_never_the_target():
    # Live proof: evidence/runtime/window-20261006-192917/frame-0001.json is the
    # prompt the entry page raises ("Will you enter Mirror of Names and Spiders?").
    # It carries the dialog's own Enter while the page's Enter [1606,718,112,44]
    # stays visible underneath, so the two must not be confused.
    dialog_enter = [1124, 704, 90, 42]
    cancel = [708, 704, 152, 42]
    plan = plan_step('ENTRY_CONFIRM',
                     controls={'entry_confirm.confirm_button': dialog_enter,
                               'entry_confirm.cancel_button': cancel})
    assert plan['action'] == CLICK
    assert plan['target'] == dialog_enter
    assert plan['reason'] == 'the_entry_confirmation_starts_the_run'
    assert successor_ok(plan, 'MAP') and successor_ok(plan, 'UNKNOWN')
    assert not successor_ok(plan, 'ENTRY_CONFIRM')
    missing = plan_step('ENTRY_CONFIRM', controls={})
    assert missing['action'] == RECORD
    assert missing['reason'] == 'entry_confirm_button_not_anchored'
    # X Cancel cancels the run the player just asked for, so it may never be the
    # landing spot - not by naming it, and not through a mis-registered anchor.
    named = plan_step('ENTRY_CONFIRM', controls={'entry_confirm.cancel_button': cancel})
    assert named['action'] == RECORD
    misregistered = plan_step('ENTRY_CONFIRM',
                              controls={'entry_confirm.confirm_button': cancel,
                                        'entry_confirm.cancel_button': cancel})
    assert misregistered['action'] == RECORD
    assert misregistered['reason'] == 'control_is_forbidden'


def test_the_mirror_entry_page_uses_its_own_enter_button():
    # Live proof: evidence/runtime/window-20261006-192906/frame-0001.json is the
    # bright entry page. The same page dim (mean 16.0, Enter band mean 6.3) is what
    # the guide overlay produces; pressing Before Entry lifts it (mean 30.7, Enter
    # band 76.0) and only then does this button answer.
    enter = [1606, 718, 112, 44]
    plan = plan_step('MIRROR_ENTRY', controls={'entry.enter_button': enter})
    assert plan['action'] == CLICK
    assert plan['target'] == enter
    assert plan['reason'] == 'before_entry_enter_starts_the_free_run'
    assert successor_ok(plan, 'ENTRY_CONFIRM')
    assert not successor_ok(plan, 'MIRROR_ENTRY')
    # The pipeline spells this page both ways and both must plan identically.
    other = plan_step('BEFORE_ENTRY', controls={'entry.enter_button': enter})
    assert ({k: v for k, v in plan.items() if k != 'page'} ==
            {k: v for k, v in other.items() if k != 'page'})
    missing = plan_step('MIRROR_ENTRY', controls={})
    assert missing['action'] == RECORD
    assert missing['reason'] == 'entry_enter_button_not_anchored'


def test_reward_card_is_picked_before_confirm_and_cancel_is_never_the_target():
    # Live proof: evidence/runtime/window-20261006-034714/frame-0022.json is the
    # pick-one screen a cleared node hands back ("Selectable 0/1").
    controls = {'reward_card.card_01': [700, 300, 270, 370],
                'reward_card.card_02': [1000, 300, 270, 370],
                'reward_card.confirm_button': [1128, 764, 168, 49],
                'reward_card.cancel_button': [688, 768, 154, 45]}
    empty = plan_step('REWARD_CARD', controls=controls,
                      reward={'chosen': 0, 'required': 1})
    assert empty['action'] == CLICK
    assert empty['target'] == [700, 300, 270, 370]
    assert empty['expect'] == [ANY]
    assert empty['advance'] is True
    assert empty['reason'] == 'the_reward_card_must_be_picked_before_confirm'
    picked = plan_step('REWARD_CARD', controls=controls,
                       reward={'chosen': 1, 'required': 1})
    assert picked['action'] == CLICK
    assert picked['target'] == [1128, 764, 168, 49]
    assert picked['reason'] == 'confirm_grants_the_picked_encounter_reward'
    # A missing counter is read as "nothing picked yet", never as "confirm now".
    unread = plan_step('REWARD_CARD', controls=controls)
    assert unread['target'] == [700, 300, 270, 370]
    no_card = plan_step('REWARD_CARD',
                        controls={'reward_card.confirm_button': [1128, 764, 168, 49]})
    assert no_card['action'] == RECORD
    assert no_card['reason'] == 'reward_card_box_not_anchored'
    # Cancel refuses the reward, so it is registered but never a plan target.
    cancel = [688, 768, 154, 45]
    named = plan_step('REWARD_CARD', controls={'reward_card.card_01': cancel,
                                               'reward_card.cancel_button': cancel})
    assert named['action'] == RECORD
    assert named['reason'] == 'control_is_forbidden'


def test_the_shop_page_only_ever_leaves():
    # Live proof: evidence/runtime/window-20261006-042123/frame-0001.json is the
    # Shop node the encounter panel's Enter handed back. The module budget is
    # 0/pending, so Leave is the only input; buying, refreshing, healing, fusing
    # and selling stay unanchored on purpose.
    controls = {'shop.leave_button': [1622, 945, 150, 53]}
    plan = plan_step('SHOP', controls=controls)
    assert plan['action'] == CLICK
    assert plan['target'] == [1622, 945, 150, 53]
    assert plan['reason'] == 'leaving_the_shop_is_the_only_budget_safe_input'
    assert successor_ok(plan, 'SHOP_LEAVE')
    assert successor_ok(plan, 'MAP')
    assert not successor_ok(plan, 'BATTLE_HUD')
    missing = plan_step('SHOP', controls={})
    assert missing['action'] == RECORD
    assert missing['reason'] == 'shop_leave_button_not_anchored'


def test_the_shop_exit_confirmation_confirms_and_never_cancels():
    # Live proof: evidence/runtime/window-20261006-042529/frame-0002.json is what
    # leaving the shop asks back ("Leave the shop?" with X Cancel / Confirm).
    controls = {'shop.leave_confirm_button': [1116, 722, 110, 34]}
    plan = plan_step('SHOP_LEAVE', controls=controls)
    assert plan['action'] == CLICK
    assert plan['target'] == [1116, 722, 110, 34]
    assert plan['reason'] == 'confirming_the_shop_exit_is_the_only_forward_input'
    assert successor_ok(plan, 'MAP')
    missing = plan_step('SHOP_LEAVE', controls={})
    assert missing['action'] == RECORD
    assert missing['reason'] == 'shop_leave_confirm_not_anchored'


def test_the_gift_get_notice_is_cleared_with_its_own_confirm():
    # Live proof: evidence/runtime/window-20261006-042956/frame-0001.json is the
    # "E.G.O Gift GET!" notice the reward card's Confirm raised.
    controls = {'gift_get.confirm_button': [922, 774, 136, 45]}
    plan = plan_step('GIFT_GET', controls=controls)
    assert plan['action'] == CLICK
    assert plan['target'] == [922, 774, 136, 45]
    assert plan['reason'] == 'the_gift_get_notice_is_cleared_with_its_own_confirm'
    # One notice per picked gift, so the page may hand back to itself: live
    # window-20261006-043531 shows Phlebotomy Pack then Bloody Gadget.
    assert successor_ok(plan, 'GIFT_GET')
    assert successor_ok(plan, 'REWARD_CARD')
    assert successor_ok(plan, 'MAP')
    missing = plan_step('GIFT_GET', controls={})
    assert missing['action'] == RECORD
    assert missing['reason'] == 'gift_get_confirm_not_anchored'


def test_the_node_panel_enter_may_fade_back_through_the_map():
    # Live: window-20261006-042056 shows Enter landing on a MAP frame before the
    # node content (that run's next observation was the Shop page).
    plan = plan_step('NODE_PANEL', controls=CONTROLS)
    assert successor_ok(plan, 'MAP')
    assert successor_ok(plan, 'SHOP')
    assert successor_ok(plan, 'PRE_BATTLE_TEAM')


def test_the_floor_gift_pick_is_counter_driven_and_refuse_is_never_the_target():
    # Live proof: evidence/runtime/window-20261006-043102/frame-0003.json is the
    # floor's gift pick (Acquire E.G.O Gift x4, Select 0/2, Refuse Gift).
    controls = {'gift_pick.card_01': [337, 300, 240, 200],
                'gift_pick.card_02': [732, 300, 240, 200],
                'gift_pick.card_03': [1128, 300, 240, 200],
                'gift_pick.card_04': [1526, 300, 240, 200],
                'gift_pick.select_button': [1620, 851, 100, 36],
                'gift_pick.refuse_button': [1350, 851, 150, 34]}
    empty = plan_step('GIFT_PICK', controls=controls,
                      gift={'chosen': 0, 'required': 2})
    assert empty['action'] == CLICK
    assert empty['target'] == [337, 300, 240, 200]
    assert empty['expect'] == [ANY]
    assert empty['advance'] is True
    assert empty['reason'] == 'the_floor_gift_card_must_be_picked_before_select'
    one = plan_step('GIFT_PICK', controls=controls, gift={'chosen': 1, 'required': 2})
    assert one['target'] == [732, 300, 240, 200]
    full = plan_step('GIFT_PICK', controls=controls, gift={'chosen': 2, 'required': 2})
    assert full['target'] == [1620, 851, 100, 36]
    assert full['reason'] == 'select_takes_the_picked_floor_gifts'
    # The pick page itself lingers while the notice animates in (live:
    # window-20261006-043531 read GIFT_PICK in the settle frame right after Select
    # and raised the "E.G.O Gift GET!" notice only on the next observation), so the
    # page handing back to itself is accepted; the loop guard bounds a dead button.
    assert successor_ok(full, 'GIFT_PICK')
    assert successor_ok(full, 'GIFT_GET')
    assert successor_ok(full, 'MAP')
    # A missing counter is read as "nothing picked yet", never as "select now".
    unread = plan_step('GIFT_PICK', controls=controls)
    assert unread['target'] == [337, 300, 240, 200]
    # The three-card round prints no counter at all (live:
    # evidence/runtime/window-20261006-043531), so the driver's own count and the
    # Select button's brightness carry the pick: dark -> next card, lit -> select.
    dark = plan_step('GIFT_PICK', controls=controls,
                     gift={'chosen': 1, 'required': None, 'ready': False})
    assert dark['target'] == [732, 300, 240, 200]
    assert dark['reason'] == 'the_floor_gift_card_must_be_picked_before_select'
    lit = plan_step('GIFT_PICK', controls=controls,
                    gift={'chosen': 1, 'required': None, 'ready': True})
    assert lit['target'] == [1620, 851, 100, 36]
    assert lit['reason'] == 'select_takes_the_picked_floor_gifts'
    # The button lights up as soon as one choice is made, so a readable counter has to
    # outrank brightness: live window-20261006-052152 pressed Select at "1/2" and the
    # game answered with "You have remaining E.G.O Gift choices."
    early = plan_step('GIFT_PICK', controls=controls,
                      gift={'chosen': 1, 'required': 2, 'ready': True})
    assert early['target'] == [732, 300, 240, 200]
    assert early['reason'] == 'the_floor_gift_card_must_be_picked_before_select'
    # Four cards offered and the button still dark: repeating a pick would be a
    # guess, so the page refuses instead of clicking a card again.
    exhausted = plan_step('GIFT_PICK', controls=controls,
                          gift={'chosen': 4, 'required': None, 'ready': False})
    assert exhausted['action'] == RECORD
    assert exhausted['reason'] == 'gift_pick_cards_exhausted_without_a_lit_select'
    # Refuse Gift is anchored so the page is identifiable, but never a target.
    refuse = [1350, 851, 150, 34]
    named = plan_step('GIFT_PICK', controls={'gift_pick.card_01': refuse,
                                             'gift_pick.refuse_button': refuse})
    assert named['action'] == RECORD
    assert named['reason'] == 'control_is_forbidden'
    no_cards = plan_step('GIFT_PICK',
                         controls={'gift_pick.select_button': [1620, 851, 100, 36]})
    assert no_cards['action'] == RECORD
    assert no_cards['reason'] == 'gift_pick_card_not_anchored'


def test_the_theme_pack_page_is_pulled_down_and_never_clicked():
    # Live: evidence/runtime/window-20261006-044113/frame-0001.json is the floor 2
    # theme pack page ("SELECT FLOOR 2 THEME PACK", "Select a Pack And Pull").
    controls = {'theme_packs.pack_01': [520, 390, 250, 300],
                'theme_packs.pull_to': [600, 900, 90, 60]}
    plan = plan_step('THEME_PACKS', controls=controls)
    assert plan['action'] == SWIPE
    assert plan['target'] == [520, 390, 250, 300]
    assert plan['to'] == [645, 930]
    assert plan['duration_ms'] == 700
    assert plan['reason'] == 'the_floor_theme_pack_is_pulled_down_to_be_taken'
    # The page must hand back something other than itself: a drag that did nothing
    # cannot be recorded as progress.
    assert plan['expect'] == [ANY]
    assert successor_ok(plan, 'THEME_PACKS') is False
    assert successor_ok(plan, 'MAP') is True
    assert successor_ok(plan, 'UNKNOWN') is True
    # Without the pack box, or without a pull target, the page refuses to guess.
    assert plan_step('THEME_PACKS', controls={})['reason'] == 'theme_pack_card_not_anchored'
    half = plan_step('THEME_PACKS', controls={'theme_packs.pack_01': [520, 390, 250, 300]})
    assert half['action'] == RECORD
    assert half['reason'] == 'theme_pack_pull_target_not_anchored'


def test_the_cutscene_is_skipped_once_and_never_left_waiting():
    # Live: evidence/runtime/window-20261006-044556/frame-0023.json is the abnormality
    # intro ("A thing wearing human skin was dancing in place…") with REC and SKIP.
    controls = {'cutscene.skip_button': [1620, 919, 152, 99]}
    plan = plan_step('CUTSCENE', controls=controls)
    assert plan['action'] == CLICK
    assert plan['target'] == [1620, 919, 152, 99]
    assert plan['reason'] == 'the_cutscene_is_skipped_to_resume_the_run'
    # Skipping can move the story on without changing the scene (live run70: SKIP left a
    # frame that still read CUTSCENE), so the same page counts when the frame changed,
    # and a scene that is truly gone passes outright.
    assert plan['expect'] == ['CUTSCENE', ANY]
    assert plan['advance'] is True
    assert successor_ok(plan, 'CUTSCENE') is False
    assert successor_ok(plan, 'MAP') is True
    assert step_result(plan, sent='click', before='CUTSCENE', after='CUTSCENE',
                       page='CUTSCENE', frame_changed=True)['passed'] is True
    assert step_result(plan, sent='click', before='CUTSCENE', after='CUTSCENE',
                       page='CUTSCENE', frame_changed=False)['passed'] is False
    assert plan_step('CUTSCENE', controls={})['reason'] == 'cutscene_skip_not_anchored'


def test_the_event_choice_takes_the_row_that_names_its_reward():
    # Live: evidence/runtime/window-20261006-044943/frame-0015.json has three rows and
    # the hint "Select to gain a Blunt E.G.O Gift" under the second one.
    rows = [[1096, 311, 290, 28], [1096, 464, 378, 28], [1096, 643, 366, 33]]
    plan = plan_step('EVENT_CHOICE', candidates=rows, candidate_index=1)
    assert plan['action'] == CLICK
    assert plan['target'] == [1096, 464, 378, 28]
    assert plan['reason'] == 'the_event_choice_that_names_its_reward_is_taken'
    assert plan['detail'] == {'option_count': 3, 'option_index': 1}
    # Any row advances, so the plan is proven by the page being gone - or by the page
    # changing under the same scene name while the row's outcome is narrated.
    assert plan['expect'] == ['EVENT_CHOICE', ANY]
    assert plan['advance'] is True
    assert successor_ok(plan, 'EVENT_CHOICE') is False
    assert successor_ok(plan, 'MAP') is True
    # No rows read, or an index outside them, refuses instead of clicking blind.
    assert plan_step('EVENT_CHOICE')['reason'] == 'no_event_choice_observed'
    bad = plan_step('EVENT_CHOICE', candidates=rows, candidate_index=3)
    assert bad['action'] == RECORD
    assert bad['reason'] == 'event_choice_index_out_of_range'


def test_the_event_result_is_tapped_through_and_then_continued():
    # Live: evidence/runtime/window-20261006-045451/frame-0001.json is the outcome page
    # with the bottom-right control still dim; one tap on the story panel produced
    # frame-0002.json, whose Continue is the only control left.
    controls = {'event_result.story_panel': [300, 400, 500, 250],
                'event_result.continue_button': [1588, 943, 218, 55]}
    tap = plan_step('EVENT_RESULT', controls=controls)
    assert tap['action'] == CLICK
    assert tap['target'] == [300, 400, 500, 250]
    assert tap['reason'] == 'the_event_result_story_is_tapped_to_reveal_its_continue'
    assert tap['advance'] is True
    # The tap only relights the button, so the same page may come back: the frame
    # change is what proves it, not the page name.
    assert successor_ok(tap, 'EVENT_RESULT') is False
    assert successor_ok(tap, 'EVENT_RESULT_READY') is True
    assert step_result(tap, sent='click', before='EVENT_RESULT', after='EVENT_RESULT',
                       page='EVENT_RESULT', frame_changed=False)['passed'] is False
    assert step_result(tap, sent='click', before='EVENT_RESULT', after='EVENT_RESULT',
                       page='EVENT_RESULT', frame_changed=True)['passed'] is True
    done = plan_step('EVENT_RESULT_READY', controls=controls)
    assert done['action'] == CLICK
    assert done['target'] == [1588, 943, 218, 55]
    assert done['reason'] == 'the_event_result_is_cleared_with_its_own_continue'
    assert done['expect'] == ['EVENT_RESULT_READY', ANY]
    assert done['advance'] is True
    assert successor_ok(done, 'EVENT_RESULT_READY') is False
    assert successor_ok(done, 'MAP') is True
    # No story panel, or no continue button, refuses rather than clicking blind.
    assert plan_step('EVENT_RESULT', controls={})['reason'] == 'event_result_story_panel_not_anchored'
    assert plan_step('EVENT_RESULT_READY', controls={})['reason'] == 'event_result_continue_not_anchored'


def test_the_deployment_view_only_starts_the_fight():
    # Live run build/window-run29.json: To Battle! on the team page handed back
    # DEPLOYMENT, whose own bottom-right control is the same button
    # (evidence/runtime/window-20261006-050402/frame-0006.json).
    controls = {'pre_battle.battle_button': [1674, 859, 144, 44]}
    plan = plan_step('DEPLOYMENT', controls=controls)
    assert plan['action'] == CLICK
    assert plan['target'] == [1674, 859, 144, 44]
    assert plan['reason'] == 'deployment_view_starts_the_fight'
    assert 'BATTLE_HUD' in plan['expect']
    assert successor_ok(plan, 'BATTLE_HUD') is True
    assert successor_ok(plan, 'DEPLOYMENT') is False
    # The team page may also hand back the deployment view instead of the fight.
    team = plan_step('PRE_BATTLE_TEAM', controls=controls)
    assert 'DEPLOYMENT' in team['expect']
    assert successor_ok(team, 'DEPLOYMENT') is True
    assert plan_step('DEPLOYMENT', controls={})['reason'] == 'deployment_battle_button_not_anchored'


def test_the_left_over_gift_warning_cancels_and_never_trades_the_gifts():
    # Live proof: pressing Select at "1/2" raised "You have remaining E.G.O Gift
    # choices. Will you proceed without selecting an E.G.O Gift?" (evidence/runtime/
    # window-20261006-052152/frame-0003.json). Its Confirm trades the remaining gifts
    # for random Trials -- the refusal the user forbade -- so Cancel is the only input.
    cancel = [704, 718, 142, 42]
    controls = {'gift_warning.cancel_button': cancel,
                'gift_warning.confirm_button': [1068, 718, 156, 36]}
    plan = plan_step('GIFT_WARNING', controls=controls)
    assert plan['action'] == CLICK
    assert plan['target'] == cancel
    assert plan['reason'] == 'the_warning_is_cancelled_to_keep_the_remaining_gift_choices'
    assert successor_ok(plan, 'GIFT_PICK')
    missing = plan_step('GIFT_WARNING', controls={'gift_warning.confirm_button': controls['gift_warning.confirm_button']})
    assert missing['action'] == RECORD
    assert missing['reason'] == 'gift_warning_cancel_not_anchored'
    named = plan_step('GIFT_WARNING',
                      controls={'gift_warning.cancel_button': controls['gift_warning.confirm_button'],
                                'gift_warning.confirm_button': controls['gift_warning.confirm_button']})
    assert named['action'] == RECORD
    assert named['reason'] == 'control_is_forbidden'

def test_the_gift_warning_is_named_from_a_live_frame():
    locale = json.loads((Path(__file__).resolve().parents[1]
                         / 'assets/resource/en/locale.json').read_text())
    frame = json.loads((Path(__file__).resolve().parents[1]
                        / 'evidence/runtime/window-20261006-052152/frame-0003.json').read_text())
    records = [Text(t['text'], tuple(t['box']), t['score']) for t in frame['ocr']]
    assert classify(records, locale, tuple(frame['size'])) == 'GIFT_WARNING'


def test_the_skill_check_is_rolled_by_the_best_odds_and_never_skipped():
    # Live proof: evidence/runtime/window-20261006-204421/frame-0001.json prints an odds
    # caption over each identity card, and card 1 (VeryHigh) is the one worth sending.
    # The driver reads the row and hands that card's box over; the page has no anchored
    # control of its own, because the row is read live. Picking the card keeps the page
    # (evidence/runtime/window-20261006-205435/frame-0002.json is the same page after the
    # click), so the step passes on the changed frame rather than on a new scene.
    card = [76, 923, 84, 113]
    plan = plan_step('EVENT_CHECK', check={'slot': 1, 'tier': 'very_high', 'box': card})
    assert plan['action'] == CLICK
    assert plan['target'] == card
    assert plan['reason'] == 'the_skill_check_is_rolled_by_the_best_odds'
    assert plan['detail'] == {'slot': 1, 'tier': 'very_high'}
    assert plan['expect'] == ['EVENT_CHECK', ANY]
    assert plan['advance'] is True
    assert not successor_ok(plan, 'EVENT_CHECK')
    assert step_result(plan, sent=True, before='EVENT_CHECK', after='EVENT_CHECK',
                       page='EVENT_CHECK', frame_changed=True)['passed']
    assert not step_result(plan, sent=True, before='EVENT_CHECK', after='EVENT_CHECK',
                           page='EVENT_CHECK', frame_changed=False)['passed']
    # No slot read means no input at all: the check is never guessed at.
    unread = plan_step('EVENT_CHECK', check=None)
    assert unread['action'] == RECORD
    assert unread['reason'] == 'no_event_check_candidate_observed'
    # SKIP means nobody attempts the roll, which forfeits the check, so a mis-registered
    # anchor can never send it.
    skip = [1628, 929, 138, 83]
    named = plan_step('EVENT_CHECK', controls={'event_check.skip_button': skip},
                      check={'slot': 1, 'box': skip})
    assert named['action'] == RECORD
    assert named['reason'] == 'control_is_forbidden'


def test_the_chosen_skill_check_identity_is_committed_with_its_commence():
    # Live proof: evidence/runtime/window-20261006-205435/frame-0002.json is the same
    # check page after an identity was picked - it prints 'Predicted Odds: Very High' and
    # 'Commence' [1578,946,240,48] where the untouched page had SKIP, and the driver
    # reports that stage instead of aiming at a second card.
    box = [1578, 946, 240, 48]
    plan = plan_step('EVENT_CHECK', controls={'event_check.commence_button': box},
                     check={'stage': 'commence'})
    assert plan['action'] == CLICK
    assert plan['target'] == box
    assert plan['reason'] == 'the_skill_check_is_committed_with_its_commence'
    assert successor_ok(plan, 'CUTSCENE') and successor_ok(plan, 'EVENT_RESULT_READY')
    assert not successor_ok(plan, 'EVENT_CHECK') or plan['advance'] is True
    # A registration without the button sends nothing.
    missing = plan_step('EVENT_CHECK', check={'stage': 'commence'})
    assert missing['action'] == RECORD
    assert missing['reason'] == 'event_check_commence_not_anchored'


def test_the_resolved_skill_check_is_tapped_through_its_story_panel():
    # Live proof: evidence/runtime/window-20261006-205922/frame-0025.json kept the page
    # for 43 frames with 'Check Passed' and the story already complete, and the only frame
    # whose OCR reaches the bottom-right control is frame-0001. The user's rule (m10140) is
    # to keep tapping the small screen until that control lights up, so the story panel is
    # the target and the tap is judged by the frame, not by the page name.
    panel = [206, 181, 756, 325]
    plan = plan_step('EVENT_CHECK_RESULT',
                     controls={'event_check_result.story_panel': panel})
    assert plan['action'] == CLICK
    assert plan['target'] == panel
    assert plan['reason'] == ('the_check_outcome_is_tapped_through_until_its_control'
                              '_lights_up')
    assert plan['advance'] is True
    assert successor_ok(plan, 'CUTSCENE')
    assert step_result(plan, sent=True, before='EVENT_CHECK_RESULT',
                       after='EVENT_CHECK_RESULT', page='EVENT_CHECK_RESULT',
                       frame_changed=True)['passed']
    assert not step_result(plan, sent=True, before='EVENT_CHECK_RESULT',
                           after='EVENT_CHECK_RESULT', page='EVENT_CHECK_RESULT',
                           frame_changed=False)['passed']
    # A registration without the panel sends nothing rather than guessing a coordinate.
    missing = plan_step('EVENT_CHECK_RESULT')
    assert missing['action'] == RECORD
    assert missing['reason'] == 'event_check_result_panel_not_anchored'


def test_the_lit_control_of_the_resolved_skill_check_leaves_it():
    # Live proof: evidence/runtime/window-20261006-210803/frame-0002.json is the same page
    # after the story was tapped through, with 'Continue' [1588,941,220,59] lit in the slot
    # that read nothing at all in frame-0001.json. The roll is already resolved, so this
    # control is how the page is left - it is not the SKIP that forfeits a check.
    box = [1588, 941, 220, 59]
    plan = plan_step('EVENT_CHECK_READY',
                     controls={'event_check_ready.continue_button': box})
    assert plan['action'] == CLICK
    assert plan['target'] == box
    assert plan['reason'] == 'the_check_outcome_is_left_with_its_lit_continue'
    assert plan['advance'] is True
    assert successor_ok(plan, 'MAP') and successor_ok(plan, 'CUTSCENE')
    missing = plan_step('EVENT_CHECK_READY')
    assert missing['action'] == RECORD
    assert missing['reason'] == 'event_check_ready_continue_not_anchored'
