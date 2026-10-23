"""Both producers of `window_recovery` must write the same fields.

Measured regression: `evidence/runtime/packaged-mirror-20261023-085334` recorded a
recovery from the pinch-the-map-first path with no `refused_kind`, so the audit saw
it as silent although the kind was derivable.
"""
import ast
import pathlib

import pytest

from maalimbus.pages import kind_of

RUNNER = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'maalimbus' / 'runner.py'


def _note_calls(source):
    tree = ast.parse(source)
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != 'note':
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        if node.args[0].value == 'window_recovery':
            calls.append(node)
    return calls


def test_every_recovery_writer_goes_through_the_shared_fields():
    source = RUNNER.read_text(encoding='utf-8')
    calls = _note_calls(source)
    assert len(calls) >= 2, 'expected the pinch path and the ladder path'
    for call in calls:
        keywords = {kw.arg for kw in call.keywords}
        # `refused_kind`/`recovery_action`/`deciding_kind` are not spelled per call:
        # they arrive through `**self._recovery_fields(...)`.
        spread = [kw for kw in call.keywords if kw.arg is None]
        assert spread, f'recovery note at line {call.lineno} builds its own fields'
        assert not ({'refused_kind', 'recovery_action', 'deciding_kind'} & keywords), (
            f'recovery note at line {call.lineno} re-spells a shared field')


def test_the_shared_fields_name_the_kind_from_a_runner_stop_reason():
    assert kind_of(stopped_reason='unexpected_successor') == 'bad_saved_state'
    assert kind_of(stopped_reason='page_unreadable_after_waiting') == 'unreadable_text'
