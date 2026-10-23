"""Every plan that sends an input states what disproves it, or says it cannot.

A plan can be wrong in two visible ways today: the next page is not in its ``expect``
set (``window.successor_ok`` says so, and the runner answers ``unexpected_successor``),
or a hook in the runner reads the word back and checks something the screen does not
show.  A plan with neither is not *unchecked by accident* -- it is a decision nobody has
written down, and the count of those was 28 of 80 acting plans on 2026-10-23.

The gate below fails when a new acting plan has no proof and is not declared, when a
declared word stops being an acting plan, and when the count grows.  It also proves the
two counter-examples: a hand-made plan with no expectation is reported, and a word that
gained an expectation is no longer reported.
"""
import ast
import json
from pathlib import Path

import maalimbus.plan_reasons as plan_reasons
import maalimbus.window as window
from maalimbus import pages
from maalimbus.runner import FakeDevice, MirrorRunner

import maalimbus.runner as runner


DECLARED_BASELINE = 28


def test_the_relation_matches_the_declaration():
    assert set(plan_reasons.unproven()) == set(pages.PLANS_WITHOUT_PROOF)


def test_the_declared_words_are_acting_plans():
    acting = plan_reasons.acting_plans()
    for word in pages.PLANS_WITHOUT_PROOF:
        assert word in acting, word
        assert set(acting[word]['actions']) - {'record'}, word


def test_the_unmeasured_count_only_shrinks():
    assert len(plan_reasons.unproven()) <= DECLARED_BASELINE
    assert len(pages.PLANS_WITHOUT_PROOF) <= DECLARED_BASELINE


def test_every_declared_word_is_marked_unmeasured():
    # A declared word may only carry a class once a run has observed it: the value is
    # the evidence, so an invented successor set would be worse than the gap.
    assert set(pages.PLANS_WITHOUT_PROOF.values()) == {'unmeasured'}


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
    assert not set(hooked) & set(pages.PLANS_WITHOUT_PROOF)


def test_a_refusal_owes_no_proof():
    acting = plan_reasons.acting_plans()
    refused = set(plan_reasons.producers()['window']) - set(acting)
    assert 'candidate_index_out_of_range' in refused
    assert not refused & set(pages.PLANS_WITHOUT_PROOF)


def test_the_table_rows_all_carry_an_expectation():
    # The 27 step rows are data, so their expectation is data: a row that lost it would
    # be an unproven click nobody declared.
    for page, row in window.STEP_ROWS.items():
        assert row.get('expect'), page
        assert page not in pages.PLANS_WITHOUT_PROOF


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

