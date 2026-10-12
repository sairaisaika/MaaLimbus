"""Tests for the one file a person reads after a mirror run goes red.

The complaint that produced this module was that the log does not make clear why
the automatic mirror task turned red and stopped. `events.jsonl` stays the machine
record; `event_log.report` renders the same facts as one line per step plus a named
stop reason and a sentence about what it means.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import event_log  # noqa: E402

#: the shape of the user's failed run of 2026-10-12 01:00 (dist evidence, pi-20261012-010039)
SWALLOWED = {
    'controller': 'adb', 'address': '127.0.0.1:16416',
    'run_ledger': {'run': '4734bfe68803421c8d261dccbc9120be', 'team': 7, 'rotation': 5,
                   'path': 'config/user-run-ledger.json'},
    'observation': {'scene': 'DUNGEON_TEAM'}, 'passed': False,
    'reason': 'unexpected_successor', 'clicks_sent': 1,
    'steps': [{'step': 1, 'page_before': 'DUNGEON_TEAM', 'scene_after': 'DUNGEON_TEAM',
               'passed': False, 'stopped': 'click_was_swallowed_by_the_game',
               'click_point': [187, 791], 'frame': 'frame-0001',
               'observation': {'scene': 'DUNGEON_TEAM'},
               'plan': {'action': 'click', 'target': [148, 778, 92, 26],
                        'reason': 'dungeon_team_slot_is_selected_for_the_rotation'}}],
}


def test_every_step_gets_one_line_and_its_own_why():
    text = event_log.report(SWALLOWED, extra=['input helpers: MISSING in C:/app/maafw/MaaAgentBinary'])
    assert any('#  1  DUNGEON_TEAM' in line and 'click (194,791)' in line and 'STOPPED' in line
               for line in text.splitlines()), text
    assert 'why: dungeon_team_slot_is_selected_for_the_rotation' in text
    assert 'sent: tap 187,791' in text
    assert 'frame: frame-0001.png' in text
    assert 'ledger: run 4734bfe68803421c8d261dccbc9120be team 7 rotation 5' in text
    assert 'page: DUNGEON_TEAM (before any input)' in text
    assert 'input helpers: MISSING in C:/app/maafw/MaaAgentBinary' in text


def test_the_stop_is_named_and_explained():
    text = event_log.report(SWALLOWED)
    assert 'STOPPED after 1 steps (1 clicks sent): unexpected_successor' in text
    explanation = text.split('STOPPED after 1 steps')[-1]
    assert 'input helpers' in explanation and 'swallowed tap' in explanation


def test_a_proven_step_shows_where_it_landed():
    lines = event_log.step_lines({'step': 3, 'page_before': 'MIRROR_ENTRY',
                                  'scene_after': 'ENTRY_CONFIRM', 'passed': True,
                                  'plan': {'action': 'click', 'target': [1606, 718, 112, 44],
                                           'reason': 'before_entry_enter_starts_the_free_run'}},
                                 3)
    assert lines[0].startswith('  #  3  MIRROR_ENTRY')
    assert 'click (1662,740)' in lines[0] and 'ok -> ENTRY_CONFIRM' in lines[0]
    assert 'why: before_entry_enter_starts_the_free_run' in lines[1]


def test_a_passing_window_says_passed():
    text = event_log.report({'passed': True, 'reason': 'window_steps_passed', 'steps': []})
    assert 'PASSED after 0 steps (0 clicks sent): window_steps_passed' in text
    assert '(no step was planned)' in text
    assert 'every planned input in this window was proven' in text


def test_a_record_only_step_prints_no_coordinates():
    lines = event_log.step_lines({'step': 1, 'page_before': 'UNKNOWN_DIALOG',
                                  'passed': False, 'stopped': 'unknown_dialog_close_not_anchored',
                                  'plan': {'action': 'record',
                                           'reason': 'unknown_dialog_close_not_anchored'}}, 1)
    assert 'no input' in lines[0]
    assert 'why: unknown_dialog_close_not_anchored' in lines[1]
    assert 'sent:' not in '\n'.join(lines)


def test_an_unknown_reason_is_printed_as_itself():
    assert event_log.explain('a_brand_new_reason') == 'a brand new reason'
    assert event_log.explain(None) == 'no reason was recorded.'


def test_a_failed_transaction_says_the_ledger_was_not_written():
    for reason in ('unverified_grace_purchase', 'floor_gift_receipt', 'initial_gift_selection'):
        assert 'nothing was written to the run ledger' in event_log.explain(reason)


def test_the_error_line_is_the_first_line_of_the_traceback():
    text = event_log.report({'passed': False, 'reason': 'mirror_loop_failed', 'steps': [],
                             'error': 'RuntimeError: boom\n  at somewhere'})
    assert '  error: RuntimeError: boom' in text
    assert 'at somewhere' not in text


def test_a_stop_that_is_a_count_prints_its_numbers():
    # Live 2026-10-12 01:56: the Grace page offered 60 starlight while the configured
    # cards cost 100, so the run refused to enter with only part of them bought. The
    # reason alone does not say which cards or how much, so the step carries the counts.
    step = {'step': 1, 'page_before': 'STAR_GRACES', 'passed': False,
            'stopped': 'configured_graces_incomplete_within_budget',
            'reason': 'configured_graces_incomplete_within_budget',
            'detail': {'requested': [2, 4, 5, 7], 'bought': [2, 4, 5], 'available': 0,
                       'budget': 60, 'unaffordable': [7]}}
    lines = event_log.step_lines(step, 2)
    assert lines[2].startswith('       detail: ')
    assert 'requested=[2, 4, 5, 7]' in lines[2]
    assert 'unaffordable=[7]' in lines[2]
    assert 'the Graces configured for this team' in event_log.explain(
        'configured_graces_incomplete_within_budget')
    assert 'could not be read from the board' in event_log.explain(
        'configured_grace_costs_not_proven')
    # A step that carries no detail prints no such line.
    plain = event_log.step_lines({'step': 1, 'page_before': 'MAP', 'passed': True}, 1)
    assert not any(line.startswith('       detail: ') for line in plain)
