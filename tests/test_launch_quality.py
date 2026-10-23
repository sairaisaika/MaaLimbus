"""A refusal must say what to do, and the device address must not be retyped."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from maalimbus import runner  # noqa: E402


def test_the_granted_nonce_is_readable(tmp_path, monkeypatch):
    path = tmp_path / 'auth.json'
    path.write_text(json.dumps({'live_input_authorized': True, 'nonce': 'abc123'}), encoding='utf-8')
    monkeypatch.setattr(runner, 'AUTHORIZATION', path)
    assert runner.granted_nonce() == 'abc123'


def test_a_withheld_grant_returns_none(tmp_path, monkeypatch):
    path = tmp_path / 'auth.json'
    path.write_text(json.dumps({'live_input_authorized': False, 'nonce': 'abc123'}), encoding='utf-8')
    monkeypatch.setattr(runner, 'AUTHORIZATION', path)
    assert runner.granted_nonce() is None


def test_an_unreadable_grant_returns_none(tmp_path, monkeypatch):
    path = tmp_path / 'auth.json'
    path.write_text('{not json', encoding='utf-8')
    monkeypatch.setattr(runner, 'AUTHORIZATION', path)
    assert runner.granted_nonce() is None


CONSTANT_ARGS = {'--address': "default='127.0.0.1:16416'",
                 '--app': "default=Path('dist/MaaLimbus')"}


def test_project_constants_are_defaults_not_requirements():
    text = (ROOT / 'tools' / 'verify_packaged_mirror_loop.py').read_text(encoding='utf-8')
    for flag, default in CONSTANT_ARGS.items():
        assert f"add_argument('{flag}', " in text
        line = [l for l in text.splitlines() if f"add_argument('{flag}', " in l][0]
        assert default in line, f"{flag} lost its project default"
        assert 'required=True' not in line, f"{flag} became a requirement again"
