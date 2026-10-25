"""A second reading of the same frame may stand in for a null party field (D287)."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')


def test_the_second_reading_happens_before_the_candidates_are_asked_for():
    probe = SOURCE.index('probe = party_probe(directory, record)')
    candidates = SOURCE.index('frame, candidates = candidates_of(directory, record')
    assert probe < candidates, 'a party filled after the candidates were asked for is not used'


def test_the_second_reading_is_journalled_and_names_its_source():
    assert "note('map_party_from_probe'" in SOURCE
    assert "source='probe' if probe_party is not None else party_anchor_source(record)" in SOURCE


def test_the_second_reading_is_handed_on_as_the_fallback_party():
    assert "fallback_party=fallback or probe_party" in SOURCE
    assert "party=record.get('map_party') or probe_party" in SOURCE


def test_the_second_reading_is_only_tried_when_the_field_is_null():
    probe = SOURCE.index('probe = party_probe(directory, record)')
    window = SOURCE[probe - 400:probe + 400]
    assert "if record.get('map_party') is None:" in window


def test_the_probe_never_raises_and_never_sends_input():
    probe = SOURCE.index('def party_probe(directory, record):')
    body = SOURCE[probe:probe + 900]
    assert 'except Exception' in body
    assert 'click' not in body and 'swipe' not in body
