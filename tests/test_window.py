"""Tests for the bounded window step planner.

The planner decides which single input a live page may receive; every case here
is a page that the live tools have already met, plus the refusals that keep an
unproven page from receiving a guessed coordinate.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.window import (ANY, CLICK, NODE, RECORD, plan_step, resolve_overlay,
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
    assert plan['expect'] == ['NODE_PANEL']
    assert successor_ok(plan, 'NODE_PANEL')


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
    assert plan['expect'] == ['PRE_BATTLE_TEAM', 'UNKNOWN']


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


def test_battle_without_a_proven_control_refuses():
    plan = plan_step('BATTLE_HUD', start_box=None, auto_assign=None)
    assert plan['action'] == RECORD
    assert plan['reason'] == 'battle_has_no_proven_control'


def test_unproven_pages_are_observe_only():
    for page in ('SHOP', 'EVENT_DIALOG', 'REWARD_SETTLE', 'FLOOR_GIFTS',
                 'BATTLE_RESULT', 'UNKNOWN'):
        plan = plan_step(page, controls=CONTROLS,
                         start_box=[1, 2, 3, 4], candidates=[[5, 6, 7, 8]])
        assert plan['action'] == RECORD, page
        assert plan['reason'] == 'page_is_observe_only'
        assert plan['target'] is None


def test_successor_outside_the_expected_set_is_recorded_as_a_failure():
    plan = plan_step('MAP', candidates=[[900, 400, 60, 60]])
    assert not successor_ok(plan, 'SHOP')
    record = step_result(plan, sent=True, before='MAP', after='SHOP', page='SHOP')
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
    # With the book's own header arrow anchored the last card is closed instead of
    # stopping: live, clicking it over the team page uncovered PRE_BATTLE_TEAM.
    closed = plan_step('TUTORIAL',
                       controls={'tutorial.next_button': [1782, 505, 76, 52],
                                 'tutorial.book_close': [83, 27, 114, 77]},
                       arrows={'previous': [93, 519, 40, 44], 'next': None})
    assert closed['action'] == CLICK
    assert closed['target'] == [83, 27, 114, 77]
    assert closed['advance'] is True
    assert closed['reason'] == 'tutorial_last_page_is_closed_from_the_book_header'
    assert successor_ok(closed, 'PRE_BATTLE_TEAM')
    assert not successor_ok(closed, 'TUTORIAL')
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
