"""Centring runs once per map branch, and never in observe-only mode."""
from types import SimpleNamespace

from maalimbus import runner


def _loop(**settings):
    data = {'rounds': 1, 'interval': 0}
    data.update(settings)
    device = SimpleNamespace(controller=object(), swipe=lambda *a, **k: None)
    loop = runner.MirrorRunner(device, settings=data, directory=None)
    loop.journal = SimpleNamespace(record=lambda *a, **k: None)
    return loop


def test_the_first_map_branch_normalises_and_the_second_does_not(monkeypatch):
    loop = _loop()
    calls, notes = [], []
    monkeypatch.setattr(runner, 'pinch_out', lambda *a, **k: calls.append('zoom'))
    monkeypatch.setattr(loop, 'note', lambda name, **fields: notes.append(name))
    loop._frame_and_record = lambda: (None, {})
    loop._normalise_view_once()
    assert calls == ['zoom'] and loop.state['view_normalised'] is True
    loop._normalise_view_once()
    assert calls == ['zoom']


def test_observe_only_never_touches_the_view(monkeypatch):
    loop = _loop(observe_only=True)
    monkeypatch.setattr(runner, 'pinch_out',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('no zoom')))
    loop._normalise_view_once()
    assert 'view_normalised' not in loop.state
