from __future__ import annotations
import importlib.util, pathlib
REPO = pathlib.Path(__file__).resolve().parents[1]

def _tool():
    spec = importlib.util.spec_from_file_location('probe_party_readers', REPO / 'tools' / 'probe_party_readers.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def test_the_four_readers_are_named():
    assert set(_tool().readings.__doc__ is not None for _ in [0])

def test_readings_asks_every_reader(monkeypatch):
    tool = _tool()
    calls = []
    for name in ('party_point', 'flame_point', 'glow_point', 'player_marker'):
        monkeypatch.setattr(tool.mv, name, (lambda n: (lambda image: calls.append(n) or (1, 2)))(name))
    out = tool.readings(None)
    assert calls == ['party_point', 'flame_point', 'glow_point', 'player_marker']
    assert out['party_point'] == (1, 2)

def test_a_missing_directory_is_no_rows(tmp_path):
    assert _tool().survey(tmp_path / 'nope') == []
