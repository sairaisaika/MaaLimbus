"""A refusal names the reading that failed, not only the one that came back empty.

The live frame evidence/runtime/packaged-mirror-20261025-061838/frame-0001.png reads eight
map candidates while `party_point` returns None; the run then ends with
`no_candidate_node_observed`, which blames the nodes.  The record now carries
`map_candidates_refused`, so the next analysis can tell the two apart.
"""
import json
import pathlib

import pytest

from maalimbus import runner

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN = ROOT / 'evidence/runtime/packaged-mirror-20261025-061838'


def test_a_party_less_frame_that_read_nodes_says_the_party_was_unread():
    frame, record = RUN / 'frame-0001.png', RUN / 'frame-0001.json'
    if not frame.exists() or not record.exists():
        pytest.skip('retained live evidence is not present')
    data = json.loads(record.read_text(encoding='utf-8'))
    _name, boxes = runner.candidates_of(RUN, data)
    assert boxes == []
    assert data['map_candidates_refused']['party'] is None
    assert data['map_candidates_refused']['read'] >= 1


def test_a_frame_that_read_nothing_still_records_why_nothing_was_offered():
    record = {'scene': 'MAP', 'frame': 'none', 'ocr': [], 'map_candidate_kinds': {}}
    assert runner.candidates_of(ROOT / 'evidence/runtime', record)[1] in (None, [])
    # A frame that read no node at all leaves the party question alone: it never got
    # as far as needing one, so it does not claim the party failed.
    assert 'map_candidates_refused' not in record
