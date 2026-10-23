"""The gate for the plan-reason vocabulary: who writes a word, who reads it.

``plan['reason']`` is prose a human reads, but inside the loop it is a key: 42 sites in
``src/maalimbus/runner.py`` ask which word a plan carries to decide what proof the sent
input owes.  Three ways that can go wrong, each with a counter-example below:

1. a hook names a word no writer produces -- a proof that can never run;
2. a reader of a *different* vocabulary (``entry['reason']``, the setting
   ``observe_only``) is counted as a plan hook, which would demand a plan writer for a
   word no plan carries;
3. a word chosen at runtime between two literals (``'a' if flag else 'b'``) is missed,
   so the report calls a real producer missing.

The fourth thing this file pins is the one plan the runner builds by hand: it carries a
word whose kind used to come from the prose model, which read "refusal" inside the
name and answered ``refused_by_policy`` -- an action of ``stop``.
"""
import ast

import pytest

from maalimbus import pages
from maalimbus import plan_reasons as reasons


def test_no_hook_names_a_word_nobody_writes():
    relation = reasons.unmatched()
    assert relation['consumers_without_producer'] == []


def test_the_hook_count_and_the_word_count_only_shrink():
    # Measured 2026-10-23 on the tree that shipped D48: 42 comparisons over 22 words,
    # 130 words the window can write, and exactly one plan the runner assembles.
    relation = reasons.unmatched()
    written = reasons.producers()
    assert relation['hooks'] <= 42, f'{relation["hooks"]} reason hooks'
    assert relation['words'] <= 22, f'{relation["words"]} words read'
    assert len(written['window']) >= 130, f'{len(written["window"])} window words'
    assert len(written['runner']) <= 1, f'{len(written["runner"])} hand-built plans'


def test_the_gate_can_fail():
    # A hook for a word nobody writes.  Without this assertion the gate above could be
    # vacuous -- the failure mode the whole module exists to catch is silence.
    source = (
        "def step(self):\n"
        "    if plan.get('reason') == 'a_word_nobody_writes':\n"
        "        return 1\n"
    )
    relation = reasons.unmatched(source)
    assert relation['consumers_without_producer'] == ['a_word_nobody_writes']


def test_the_gate_finds_a_reader_that_is_not_the_plan():
    source = (
        "def step(self):\n"
        "    if entry.get('reason') == 'observe_only':\n"
        "        return 1\n"
        "    if settings.get('reason') == 'a_setting':\n"
        "        return 2\n"
    )
    assert reasons.consumers(source) == {}


def test_every_spelling_of_a_comparison_is_read():
    source = (
        "def step(self):\n"
        "    if plan['reason'] == 'one':\n"
        "        pass\n"
        "    if 'two' == plan.get('reason'):\n"
        "        pass\n"
        "    if plan.get('reason') in ('three', 'four'):\n"
        "        pass\n"
    )
    assert set(reasons.consumers(source)) == {'one', 'two', 'three', 'four'}


def test_a_word_chosen_between_two_literals_is_two_words():
    # `window.py` picks the shelf's purchase reason with `'a' if cap else 'b'`; a reader
    # that ignored the conditional would report both as hooks nobody writes.
    source = (
        "def shelf(carrying_cap):\n"
        "    return _plan('SHOP', CLICK, reason=('a' if carrying_cap else 'b'))\n"
    )
    written = set(reasons.producers(source)['window'])
    assert {'a', 'b'} <= written
    assert written == set(reasons.VERDICT_REASONS) | {'a', 'b'}


def test_a_table_row_reason_is_a_written_word():
    source = (
        "STEP_ROWS = {'SHOP': {'control': 'enter', 'reason': 'a_row_reason',\n"
        "                      'refusal': 'shop_enter_not_anchored'}}\n"
    )
    written = set(reasons.producers(source)['window'])
    assert written == set(reasons.VERDICT_REASONS) | {'a_row_reason'}


def test_a_hand_built_plan_is_named():
    source = (
        "def step(self):\n"
        "    plan = dict(page='UNKNOWN_DIALOG', action='click',\n"
        "                reason='a_hand_built_word')\n"
    )
    assert reasons.producers(source)['runner'] == ['a_hand_built_word']


def test_the_one_hand_built_plan_is_registered():
    assert set(reasons.producers()['runner']) == set(pages.PLANNED_REASONS)


def test_every_planned_reason_is_a_known_kind():
    assert set(pages.PLANNED_REASONS.values()) <= set(pages.REFUSAL_KINDS)


def test_a_hand_built_plan_does_not_take_the_prose_fallback():
    from maalimbus.reason_kinds import kind_for

    word = 'confirm_proven_owned_gift_refusal'
    # What the prose model says on its own: the word contains "refusal".
    assert kind_for(word) == 'refused_by_policy'
    # What the literal table says now, and the action that follows from it.
    assert pages.kind_of(plan_reason=word) == 'bad_saved_state'
    assert pages.recovery_for('bad_saved_state') == 'escalate_ladder'


def test_the_literal_table_is_consulted_before_the_prose_model():
    # Reading order is REFUSALS, STOP_KINDS, PLANNED_REASONS, then prose.  A word in
    # both a literal table and the prose rules must answer from the literal table.
    assert pages.kind_of(reason='no_candidate_node_observed') == 'no_candidate'
    assert pages.kind_of(stopped_reason='unexpected_successor') == 'bad_saved_state'
    assert pages.kind_of(plan_reason='confirm_proven_owned_gift_refusal') == 'bad_saved_state'


def test_the_source_is_read_the_way_the_gate_reads_it():
    # Guards against a future refactor that renames the file the gate reads: the
    # derived side must come from real source, not from an empty parse.
    tree = ast.parse(reasons._source(reasons.RUNNER))
    assert any(isinstance(node, ast.FunctionDef) and node.name == 'step'
               for node in ast.walk(tree))


def test_the_tool_reports_a_clean_relation(capsys):
    assert reasons.main([]) == 0
    printed = capsys.readouterr().out
    assert 'hooks that name a word nobody writes: none' in printed
