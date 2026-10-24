"""Every plan that sends an input states what disproves it, or says it cannot.

A plan can be judged in three visible ways: a named successor in its ``expect`` set, the
dismissal ``expect=(ANY,)`` ("the page must change"), or a hook in the runner that reads
the word back.  An ``advance`` plan substitutes the frame for the page.

D49 read this relation as "28 of 80 acting plans have no proof at all".  That was the
instrument: ``plan_reasons._elements`` drops symbols, so ``ANY`` counted as zero and every
one of those twenty-eight carried a dismissal.  Measured 2026-10-23 after the fix: 45
named, 43 dismissing, 21 hooked, **0 unjudgeable**.  The declaration therefore moved from
"has no proof" to "is judged only by the page changing", which is weaker than a named
successor -- and for the words the archive shows never moving at all, it is wrong, which
is :data:`maalimbus.pages.PLANS_AWAITING_A_STATE_PROOF` (D56, derived in
``tests/test_plan_outcomes.py``).

The gate below fails when a new acting plan has no proof and is not declared, when a
declared word stops being an acting plan, and when a count grows.  It also proves the
counter-examples: a plan with no expectation is reported, a plan with only a dismissal is
not, and a word that gained a named successor is no longer in the dismissal set.
"""
import ast
import json
from pathlib import Path

import maalimbus.plan_reasons as plan_reasons
import maalimbus.window as window
from maalimbus import pages
from maalimbus.runner import FakeDevice, MirrorRunner

import maalimbus.runner as runner


# 28 until D57 taught the index to read the `or` fallback a plan uses to pick its word
# at runtime ("state.get('reason') or '<word>'"); the twenty-ninth was always there, the
# reader could not see it.  The thirtieth is D64: the starting-gift *row* pick used to be
# handed over through `initial['reason']`, so the reader saw the fallback word only.  The
# ratchet still only shrinks from here.
DISMISSAL_ONLY_BASELINE = 30


def test_no_acting_word_is_unjudgeable():
    # The correction D56 records: every acting plan carries some proof.
    assert plan_reasons.unproven() == []


def test_the_dismissal_only_words_are_exactly_the_declared_ones():
    acting = plan_reasons.acting_plans()
    dismissal_only = {word for word, entry in acting.items()
                      if entry['dismissal'] and not entry['expects'] and not entry['hooked']}
    assert dismissal_only == set(pages.PLANS_WITH_ONLY_A_DISMISSAL)


def test_the_declared_words_are_acting_plans():
    acting = plan_reasons.acting_plans()
    for word in pages.PLANS_WITH_ONLY_A_DISMISSAL:
        assert word in acting, word
        assert set(acting[word]['actions']) - {'record'}, word


def test_the_dismissal_only_count_only_shrinks():
    assert len(pages.PLANS_WITH_ONLY_A_DISMISSAL) <= DISMISSAL_ONLY_BASELINE


def test_every_declared_word_says_which_proof_it_lacks():
    # One word on purpose: the value names the missing proof, not a hoped-for successor.
    assert set(pages.PLANS_WITH_ONLY_A_DISMISSAL.values()) == {'page_must_change'}


def test_a_new_plan_with_no_proof_is_reported():
    source = _window_with("""
    if page == 'MAP':
        return _plan(page, CLICK, target=controls.get('node'), reason='a_new_word_no_proof')
""")
    assert 'a_new_word_no_proof' in plan_reasons.unproven(source=source)


def test_a_plan_that_states_its_successors_is_not_reported():
    source = _window_with("""
    if page == 'MAP':
        return _plan(page, CLICK, target=controls.get('node'), expect=('SHOP',),
                     reason='a_word_with_a_proof')
""")
    assert 'a_word_with_a_proof' not in plan_reasons.unproven(source=source)


def test_a_hook_is_a_proof_too():
    acting = plan_reasons.acting_plans()
    hooked = [word for word, facts in acting.items() if facts['hooked']]
    assert hooked, 'no word is proven by a hook any more; the relation is vacuous'
    assert not set(hooked) & set(pages.PLANS_WITH_ONLY_A_DISMISSAL)


def test_a_refusal_owes_no_proof():
    acting = plan_reasons.acting_plans()
    refused = set(plan_reasons.producers()['window']) - set(acting)
    assert 'candidate_index_out_of_range' in refused
    assert not refused & set(pages.PLANS_WITH_ONLY_A_DISMISSAL)


def test_the_table_rows_all_carry_an_expectation():
    # The 27 step rows are data, so their expectation is data: a row that lost it would
    # be an unproven click nobody declared.
    for page, row in window.STEP_ROWS.items():
        assert row.get('expect'), page
        assert page not in pages.PLANS_WITH_ONLY_A_DISMISSAL


def _window_with(extra):
    """The real window source with one extra branch appended to ``_plan_step``."""
    source = open(plan_reasons.WINDOW, encoding='utf-8').read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_plan_step':
            body = sorted(node.body, key=lambda n: getattr(n, 'lineno', 0))
            last = body[-1]
            lines = source.splitlines()
            lines[last.end_lineno:last.end_lineno] = [line[4:] for line in extra.splitlines()]
            return '\n'.join(lines)
    raise AssertionError('_plan_step not found')


class _Journal:
    """A journal that writes what the runner records into ``events.jsonl``."""

    def __init__(self, directory):
        self.path = Path(directory) / 'events.jsonl'

    def record(self, event, **details):
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(dict(event=event, **details), ensure_ascii=False) + '\n')


def _events(directory):
    path = Path(directory) / 'events.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def test_a_click_that_states_no_successor_is_journalled(tmp_path, monkeypatch):
    # The gap is not "the click may fail" -- it is that the loop cannot tell, so every
    # such send has to leave a record a later round can count.
    page = 'DRIVE'
    plan = {'page': page, 'action': 'click', 'target': [880, 520, 160, 48], 'node': None,
            'expect': (), 'reason': 'a_word_without_a_proof', 'advance': False}
    monkeypatch.setattr(runner, 'plan_step', lambda *args, **kwargs: dict(plan))
    monkeypatch.setattr(runner, 'observe',
                        lambda observer, deadline=None: {'scene': page,
                                                         'image_sha256': 'same',
                                                         'size': [1920, 1080], 'ocr': []})
    loop = MirrorRunner(FakeDevice(), settings={'rounds': 1, 'interval': 0, 'steps': 1,
                                                'stall_seconds': 0, 'progress_seconds': 0},
                        directory=tmp_path, journal=_Journal(tmp_path))
    loop.run(steps=1, interval=0, round_limit=1)
    notes = [event for event in _events(tmp_path)
             if event['event'] == 'input_without_a_proof']
    assert notes, [event['event'] for event in _events(tmp_path)]
    assert notes[0]['reason'] == 'a_word_without_a_proof'
    assert notes[0]['page'] == page

