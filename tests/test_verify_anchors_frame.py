"""Tests for the live-frame mode of tools/verify_anchors.py (plan section 5.2 next step)."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
for extra in (REPO / 'src', REPO / 'tools'):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import capture_anchors  # noqa: E402
import verify_anchors  # noqa: E402


def write_frame(directory, *, box=(600, 300, 80, 40), fill=200, name='frame'):
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[:, :] = 20
    left, top, width, height = box
    # a textured patch: a constant fill would make the correlation undefined
    patch = np.zeros((height, width, 3), dtype=np.uint8)
    patch[:, :] = fill
    patch[::4, :] = 40
    patch[:, ::5] = 250
    image[top:top + height, left:left + width] = patch
    png = directory / ('%s.png' % name)
    Image.fromarray(image[:, :, ::-1]).save(png)
    digest = hashlib.sha256(png.read_bytes()).hexdigest()
    (directory / ('%s.json' % name)).write_text(
        json.dumps({'image_sha256': digest, 'size': [1280, 720]}), encoding='utf-8')
    return png, digest


def registry_with_page(path):
    payload = {'version': 1, 'reference_width': 1280, 'reference_height': 720, 'note': 'test',
               'pages': [{'id': 'battle_hud', 'title': 'battle', 'evidence': [],
                          'identity': [{'id': 'battle.wave', 'kind': 'ocr', 'pattern': '^WAVE$',
                                        'roi': [0.0, 0.0, 0.3, 0.2], 'threshold': 0.8}],
                          'controls': [], 'live_derived': []}],
               'pending': []}
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def test_a_captured_template_is_confirmed_on_its_own_frame(tmp_path):
    frame, _ = write_frame(tmp_path)
    registry = tmp_path / 'anchors.json'
    registry_with_page(registry)
    capture_anchors.main(['--label', 'battle.start_label', '--from', str(frame),
                          '--box', '600,300,80,40', '--page', 'battle_hud',
                          '--registry', str(registry), '--template-root', str(tmp_path / 'base'),
                          '--image-dir', 'image/battle',
                          '--report', str(tmp_path / 'capture.json')])
    status = verify_anchors.main(['--frame', str(frame), '--registry', str(registry),
                                  '--template-root', str(tmp_path / 'base'),
                                  '--report', str(tmp_path / 'frame.json')])
    assert status == 0
    report = json.loads((tmp_path / 'frame.json').read_text(encoding='utf-8'))
    assert report['mode'] == 'frame'
    assert report['ok'] is True
    row = report['pages'][0]['controls'][0]
    assert row['hit'] is True
    assert row['expected_box'] == [600, 300, 80, 40]
    assert row['drift'] == [0, 0, 0, 0]


def test_a_moved_control_is_reported_as_drift(tmp_path):
    frame, _ = write_frame(tmp_path)
    registry = tmp_path / 'anchors.json'
    registry_with_page(registry)
    capture_anchors.main(['--label', 'battle.start_label', '--from', str(frame),
                          '--box', '600,300,80,40', '--page', 'battle_hud',
                          '--registry', str(registry), '--template-root', str(tmp_path / 'base'),
                          '--image-dir', 'image/battle',
                          '--report', str(tmp_path / 'capture.json')])
    moved, _ = write_frame(tmp_path, box=(660, 320, 80, 40), name='frame-moved')
    status = verify_anchors.main(['--frame', str(moved), '--registry', str(registry),
                                  '--template-root', str(tmp_path / 'base'),
                                  '--report', str(tmp_path / 'frame.json')])
    assert status == 1
    report = json.loads((tmp_path / 'frame.json').read_text(encoding='utf-8'))
    assert report['ok'] is False
    assert report['broken'] == [['battle_hud', 'battle.start_label', 'miss']]


def test_a_bare_frame_reads_its_size_and_sha_without_a_journal(tmp_path):
    frame, digest = write_frame(tmp_path)
    (tmp_path / 'frame.json').unlink()
    observation, image_path, computed, journal_sha = verify_anchors.frame_observation(frame)
    assert observation['size'] == [1280, 720]
    assert observation['image_sha256'] == digest == computed
    assert journal_sha is None
    assert image_path == frame


def test_a_page_without_controls_is_not_checkable_on_a_frame(tmp_path):
    frame, _ = write_frame(tmp_path)
    registry = tmp_path / 'anchors.json'
    registry_with_page(registry)
    status = verify_anchors.main(['--frame', str(frame), '--registry', str(registry),
                                  '--template-root', str(tmp_path / 'base'),
                                  '--report', str(tmp_path / 'frame.json')])
    assert status == 2  # nothing to check is not a pass
