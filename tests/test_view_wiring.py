"""The view normalisation is part of the map branch, not a helper nobody calls (D292)."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')


def test_the_map_branch_normalises_the_view_before_it_asks_for_candidates():
    call = SOURCE.index('self._normalise_view_once()')
    candidates = SOURCE.index('frame, candidates = candidates_of(directory, record')
    assert call < candidates, 'a view normalised after the candidates are read changes nothing'


def test_the_normalisation_runs_once_per_floor_only():
    body = SOURCE[SOURCE.index('def _normalise_view_once'):SOURCE.index('def _frame_and_record')]
    assert "if state.get('view_normalised') or self.settings.observe_only:" in body
    assert "state['view_normalised'] = True" in body


def test_the_event_says_what_the_view_did():
    body = SOURCE[SOURCE.index('def _normalise_view_once'):SOURCE.index('def _frame_and_record')]
    assert "note('view_normalised'" in body
    for key in ('centred', 'steps'):
        assert key in body, key
