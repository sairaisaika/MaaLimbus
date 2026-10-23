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


def test_the_device_address_has_a_project_default():
    text = (ROOT / 'tools' / 'verify_packaged_mirror_loop.py').read_text(encoding='utf-8')
    assert "add_argument('--address', default='127.0.0.1:16416')" in text
    assert "add_argument('--address', required=True)" not in text
