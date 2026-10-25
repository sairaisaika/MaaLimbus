"""A dim page is still offered its nodes, and a loose read never outranks a proven one.

Measured 2026-10-25: the same page read 18 candidates at full size and **2** on the live
1280x720 frame, whose ornaments sit below the tuned cut (7 at grey>=60, 1 at >=90, 0 at
>=175).  The relaxed read runs only when nothing else found a node, and its candidates are
added after every proven kind, so they can never displace a gold badge, a cyan step, a
path node or the boss room.
"""
import pathlib

import cv2
import pytest

from maalimbus import map_vision, runner

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIM = ROOT / 'evidence/runtime/lattice-probe/zoomed2.png'
WIDE = ROOT / 'evidence/runtime/packaged-mirror-20261025-040555/frame-0004.png'


def _clicks(path):
    image = cv2.imread(str(path))
    if image is None:
        pytest.skip(f'no retained frame at {path}')
    return map_vision.map_clicks(image, template=runner.node_badge_template())


def test_a_dim_page_is_offered_its_ornaments():
    got = _clicks(DIM)
    assert len(got) >= 8, [c['kind'] for c in got]
    assert any(c['kind'] == 'relaxed_node' for c in got)


def test_a_full_size_page_keeps_its_proven_read():
    got = _clicks(WIDE)
    assert len(got) >= 16
    assert not any(c['kind'] == 'relaxed_node' for c in got)


def test_the_relaxed_read_is_last_resort_only():
    image = cv2.imread(str(WIDE))
    if image is None:
        pytest.skip('no retained frame')
    assert map_vision.relaxed_nodes(image)          # it can read this page ...
    assert not any(c['kind'] == 'relaxed_node' for c in map_vision.map_clicks(image))  # ... but is not used
