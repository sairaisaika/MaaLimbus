"""A click the loop replaced may not be counted as the game's refusal.

`evidence/runtime/packaged-mirror-20261024-102349` clicked the lit icon at (799,482),
re-read the board, was offered a *different* set, recorded
``a_new_target_replaced_this_one_before_the_page_settled`` as a rejection, and did it
again twice -- so the refusal streak reached three off the loop's own re-planning and
the window took the progress-panel escape hatch, leaving a live exploration (the same
90 s cycle D76 measured).

A replaced target says nothing about whether the game took the click, so it is recorded
as ``superseded`` and the streak is left alone. Only a click that was followed by a
settle read of the *same* board, with the same offer, is the game's refusal.
"""
import ast
import pathlib

import maalimbus.runner as runner
from maalimbus.runner import MirrorRunner

SOURCE = pathlib.Path(runner.__file__).read_text(encoding='utf-8')
REPLACED = 'a_new_target_replaced_this_one_before_the_page_settled'


class _Journal:
    def __init__(self, directory):
        self.path = directory / 'events.jsonl'

    def record(self, event, **fields):
        import json
        row = {'event': event}
        row.update(fields)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row) + '\n')


def _loop(tmp_path):
    return MirrorRunner(runner.FakeDevice(), settings={'rounds': 1, 'interval': 0},
                        directory=tmp_path, journal=_Journal(tmp_path))


def _streak_writes(source):
    """Line numbers where the refusal streak is incremented, with their enclosing block."""
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        body = ast.dump(ast.Module(body=node.body, type_ignores=[]))
        if REPLACED not in body:
            continue
        if 'map_refused_streak' in body and '_map_verdict' in body:
            found.append(node.lineno)
    return found


def test_a_superseded_verdict_leaves_the_streak_alone(tmp_path):
    loop = _loop(tmp_path)
    loop.state['map_pending'] = [799, 482, 40, 40]
    loop._map_verdict(target=[799, 482, 40, 40], page='MAP', outcome='superseded',
                      kind='lit_icon', reason=REPLACED)
    imported = [row for row in (tmp_path / 'events.jsonl').read_text(encoding='utf-8').splitlines()
                if 'map_click_result' in row]
    assert len(imported) == 1 and 'superseded' in imported[0]
    assert loop.state.get('map_refused_streak', 0) == 0


def test_no_block_that_records_a_replaced_click_counts_it_as_a_refusal():
    assert _streak_writes(SOURCE) == []


def test_the_gate_can_fail():
    # The shape this rule replaced: the verdict and the streak increment in one block.
    old = '''
if state.get('map_pending') not in (None, list(plan['target'])):
    self._map_verdict(target=state['map_pending'], page=page, outcome='rejected',
                      reason='a_new_target_replaced_this_one_before_the_page_settled')
    state['map_refused_streak'] = int(state.get('map_refused_streak') or 0) + 1
'''
    assert _streak_writes(old) != []


def test_a_settled_rejection_still_counts(tmp_path):
    loop = _loop(tmp_path)
    loop.state['map_unjudged'] = {'target': [545, 239, 190, 190], 'kind': 'gold_badge_node',
                                  'frame': 'frame-0006'}
    assert loop._resolve_map_click('MAP') == 'rejected'
    assert loop.state['map_refused_streak'] == 1
