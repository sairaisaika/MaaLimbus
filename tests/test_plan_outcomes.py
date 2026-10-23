"""The archive's verdict on each plan word, and the gate over the words it owes.

D49 declared twenty-eight words unjudgeable.  That number was the instrument's, not the
code's: `plan_reasons._elements` drops symbols, so `expect=(ANY,)` -- "the page must
change" -- counted as no expectation at all.  Every one of the twenty-eight carried it.

Correcting the count moves the question rather than closing it.  The loop can say a sent
input moved the screen, but not, for a dismissal, *where* it moved to, and the archive
shows that for a handful of words the screen does not move at all.  Some of those are
fine: an `advance` plan is judged by the frame, so its page staying is by design.  The
rest genuinely lack a proof, and `pages.PLANS_AWAITING_A_STATE_PROOF` names them.

This file holds both halves of that statement: synthetic streams pin the reading rules,
and the retained archive is read for real when it is there.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import pages, plan_outcomes, plan_reasons  # noqa: E402


def _archive(tmp_path, name, rows):
    """Write one run's ``events.jsonl`` under ``tmp_path`` and return the directory."""
    run = tmp_path / name
    run.mkdir()
    lines = [json.dumps(row) for row in rows]
    (run / 'events.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return tmp_path


def _intent(word, page):
    return {'event': 'window_intent', 'page': page, 'reason': word}


def _scene(page):
    return {'event': 'map_observed', 'scene': page}


def test_a_changed_page_is_a_landing_and_the_same_page_is_not(tmp_path):
    _archive(tmp_path, 'one', [
        _intent('a_word', 'MAP'), _scene('SHOP'),
        _intent('a_word', 'MAP'), _scene('MAP'),
    ])
    found = plan_outcomes.outcomes(['a_word'], directory=tmp_path)
    assert found['a_word']['intents'] == 2
    assert found['a_word']['landed'] == 1
    assert found['a_word']['same'] == 1
    assert found['a_word']['successors'] == {'SHOP': 1}
    assert found['a_word']['class'] == 'mixed'


def test_a_proposal_is_not_a_page(tmp_path):
    """`semantic_frame_proposal` carries no page; reading it as one hid every landing."""
    _archive(tmp_path, 'propose', [
        _intent('a_word', 'MAP'),
        {'event': 'semantic_frame_proposal'},
        _scene('SHOP'),
    ])
    found = plan_outcomes.outcomes(['a_word'], directory=tmp_path)
    assert found['a_word']['landed'] == 1
    assert found['a_word']['no_evidence'] == 0


def test_a_heartbeat_names_the_page_the_loop_woke_on(tmp_path):
    _archive(tmp_path, 'beat', [
        _intent('a_word', 'MAP'),
        {'event': 'loop_heartbeat', 'page': 'SHOP', 'step': 4},
    ])
    assert plan_outcomes.outcomes(['a_word'], directory=tmp_path)['a_word']['landed'] == 1


def test_a_run_that_stopped_first_leaves_no_evidence(tmp_path):
    _archive(tmp_path, 'stop', [
        _intent('a_word', 'MAP'),
        {'event': 'window_no_progress', 'reason': 'the_run_kept_observing'},
    ])
    found = plan_outcomes.outcomes(['a_word'], directory=tmp_path)
    assert found['a_word']['no_evidence'] == 1
    assert found['a_word']['class'] == 'unseen'


def test_one_landing_is_not_a_pattern_and_three_are(tmp_path):
    _archive(tmp_path, 'one', [_intent('a_word', 'MAP'), _scene('SHOP')])
    assert plan_outcomes.outcomes(['a_word'], directory=tmp_path)['a_word']['class'] == 'few'
    _archive(tmp_path, 'three', [
        _intent('a_word', 'MAP'), _scene('SHOP'),
        _intent('a_word', 'MAP'), _scene('SHOP'),
        _intent('a_word', 'MAP'), _scene('SHOP'),
    ])
    assert plan_outcomes.outcomes(['a_word'], directory=tmp_path)['a_word']['class'] == 'unanimous'


def test_a_word_that_never_moves_is_never_changed_not_unseen(tmp_path):
    _archive(tmp_path, 'still', [_intent('a_word', 'MAP'), _scene('MAP')])
    assert plan_outcomes.outcomes(['a_word'], directory=tmp_path)['a_word']['class'] == 'never_changed'


def test_an_advance_plan_is_judged_by_the_pixels_and_not_by_the_page():
    """The distinction that keeps a 107-stay word out of the owed list."""
    facts = plan_reasons.acting_plans()
    if 'team_card_joins_the_next_unpicked_identity' not in facts:
        pytest.skip('the team-slot word is not in the plan vocabulary')
    assert facts['team_card_joins_the_next_unpicked_identity']['advance'] is True
    assert plan_outcomes.proof_kind('team_card_joins_the_next_unpicked_identity') == 'pixel'


def test_any_expectation_is_a_proof_so_no_acting_word_is_unjudgeable():
    assert plan_reasons.unproven() == []
    facts = plan_reasons.acting_plans()
    dismissal = [word for word, entry in facts.items()
                 if entry['dismissal'] and not entry['expects'] and not entry['advance']]
    assert dismissal, 'the dismissal-only population disappeared; re-derive D49'
    assert set(pages.PLANS_WITH_ONLY_A_DISMISSAL) & set(facts)


def test_the_counter_example_a_word_with_no_expectation_is_still_unproven():
    source = (
        'def step():\n'
        "    return _plan(page, CLICK, target=box, reason='a_word_with_nothing')\n"
    )
    assert 'a_word_with_nothing' in plan_reasons.unproven(source=source)


def test_the_counter_example_a_dismissal_is_not_unproven():
    source = (
        "ANY = 'any'\n"
        'def step():\n'
        "    return _plan(page, CLICK, target=box, expect=(ANY,), reason='a_word_that_must_move')\n"
    )
    assert 'a_word_that_must_move' not in plan_reasons.unproven(source=source)


def test_every_declared_word_is_one_the_archive_owes():
    found = plan_outcomes.outcomes()
    if not found:
        pytest.skip('no retained run carries a plan word')
    owed = {word for word, _ in plan_outcomes.needs_state_proof(found).items()
            if plan_outcomes.proof_kind(word) in (None, 'dismissal')}
    assert owed == set(pages.PLANS_AWAITING_A_STATE_PROOF)


def test_a_declared_word_that_starts_moving_is_new_evidence_not_a_silent_pass():
    """The gate is self-correcting: a landing by a declared word fails it."""
    found = {'a_declared_word': {'intents': 4, 'landed': 2, 'same': 2, 'no_evidence': 0,
                                 'successors': {'SHOP': 2}, 'from_pages': {'MAP': 4},
                                 'class': 'mixed'}}
    owed = {word for word, _ in plan_outcomes.needs_state_proof(found).items()}
    assert owed == set()


def test_the_retained_archive_is_read_the_same_way_twice():
    first = plan_outcomes.outcomes()
    if not first:
        pytest.skip('no retained run carries a plan word')
    assert first == plan_outcomes.outcomes()
    assert sum(entry['intents'] for entry in first.values()) > 0
