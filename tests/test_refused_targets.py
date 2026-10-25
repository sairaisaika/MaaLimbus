"""D302: a node the map has refused is not offered again from the same party.

Measured with `tools/audit_refused_retries.py`: 76 of 139 rejected map clicks (55%) were the
same target being refused a second time, and the worst runs refused one node four times before
stopping as `unexpected_successor`.  The verdict is what the run should remember; the box key
plus the party it was refused from is the smallest key that stays true across a party move.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

from maalimbus.runner import box_key  # noqa: E402


def _refused(box, party):
    return {(box_key(box), tuple(party) if party else None)}


def test_a_node_refused_from_this_party_is_dropped():
    refused = _refused([576, 169, 190, 190], [500, 244])
    boxes = [[576, 169, 190, 190], [384, 329, 190, 190]]
    kept = [box for box in boxes if (box_key(box), (500, 244)) not in refused]
    assert kept == [[384, 329, 190, 190]]


def test_the_same_node_is_offered_again_once_the_party_moves():
    refused = _refused([576, 169, 190, 190], [500, 244])
    moved = (700, 430)
    kept = [box for box in ([576, 169, 190, 190],) if (box_key(box), moved) not in refused]
    assert kept == [[576, 169, 190, 190]]


def test_a_different_node_is_never_dropped_by_a_neighbours_refusal():
    refused = _refused([576, 169, 190, 190], [500, 244])
    other = [580, 173, 190, 190]
    kept = [box for box in (other,) if (box_key(box), (500, 244)) not in refused]
    assert kept == [other], 'keys must be the exact box, not a radius around it'


def test_a_refusal_without_a_party_still_remembers_its_box():
    refused = _refused([576, 169, 190, 190], None)
    assert (box_key([576, 169, 190, 190]), None) in refused
