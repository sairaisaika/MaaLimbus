"""A name the observation writer uses must be bound in that module.

Measured twice this session: `party` and then `party_point` were referenced after the
local import was moved, producing `NameError` inside a callback -- which the loop then
reported as "the page could not be read". A missing name must fail here instead.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
import agent.recognition as recognition  # noqa: E402


def test_the_party_reader_is_bound_at_module_level():
    assert hasattr(recognition, 'party_point'), \
        'party_point is used by the map writer but not imported'


def test_the_map_header_helpers_are_bound():
    for name in ('map_header', 'route_decision', 'node_panel'):
        assert hasattr(recognition, name), f'{name} is used but not imported'


def test_the_writer_no_longer_hardcodes_no_party():
    source = (ROOT / 'agent' / 'recognition.py').read_text(encoding='utf-8')
    assert 'map_player=(party_point(image)' in source, \
        'the header-path writer must read the party, not assume None'
