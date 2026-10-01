import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'agent'))
from recognition import (LimbusRecognition, TeamAction, ThemeObservation,
                         DeploymentProof, BattlePlanObservation, InputPreflight,
                         LimbusTerminal, Journal)


def test_every_native_callback_has_exception_boundary():
    assert hasattr(LimbusRecognition.analyze, '__wrapped__')
    for cls in (TeamAction, ThemeObservation, DeploymentProof,
                BattlePlanObservation, InputPreflight, LimbusTerminal):
        assert hasattr(cls.run, '__wrapped__')


@pytest.mark.parametrize('broken_journal', [False, True])
def test_recognition_error_latches_actions_and_alternatives_closed(tmp_path, broken_journal):
    journal = Journal(tmp_path)
    if broken_journal:
        def reject(*args, **kwargs): raise OSError('Evidence disk unavailable')
        journal.record = reject
    rec = LimbusRecognition('en', journal)
    calls = []
    def reject_ocr(*args):
        calls.append('ocr')
        raise RuntimeError('OCR unavailable')
    rec.observe = reject_ocr
    argv = SimpleNamespace(custom_recognition_param='{"scene":"DEPLOYMENT"}',
                           node_name='DeploymentNext', image=None)
    assert rec.analyze(None, argv) is None
    assert rec.callback_failure['error_type'] == 'RuntimeError'
    assert rec.callback_failure.get('journal_failed', False) == broken_journal
    assert rec.analyze(None, argv) is None
    assert calls == ['ocr']
    assert TeamAction(rec).run(None, SimpleNamespace(custom_action_param='{}')) is False
    if not broken_journal:
        events = [json.loads(l) for l in (tmp_path/'events.jsonl').read_text().splitlines()]
        assert len(events) == 1 and events[0]['event'] == 'callback_failed'


def test_bad_action_json_cannot_escape_even_with_broken_journal(tmp_path):
    journal = Journal(tmp_path)
    def reject(*args, **kwargs): raise OSError('Evidence disk unavailable')
    journal.record = reject
    rec = LimbusRecognition('en', journal)
    action = TeamAction(rec)
    assert action.run(None, SimpleNamespace(custom_action_param='{')) is False
    assert rec.callback_failure['error_type'] == 'JSONDecodeError'
    assert rec.callback_failure['journal_failed'] is True


def test_terminal_error_returns_false_without_clear(tmp_path):
    rec = LimbusRecognition('en', Journal(tmp_path))
    assert LimbusTerminal(rec).run(None, SimpleNamespace(custom_action_param='{}')) is False
    assert rec.callback_failure['error_type'] == 'KeyError'
    assert rec.callback_failure['verified_clear'] is False
