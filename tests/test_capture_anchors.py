"""Tests for tools/capture_anchors.py (the one-command anchor harvest of plan section 5.3)."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
if str(REPO / 'tools') not in sys.path:
    sys.path.insert(0, str(REPO / 'tools'))

import capture_anchors  # noqa: E402
from maalimbus import anchors as anchor_module  # noqa: E402


def write_frame(directory, *, size=(1920, 1080), box=(1518, 738, 60, 28), name='frame-0044'):
    """A frame with a textured patch at ``box`` plus the journal json beside it."""
    image = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    image[:, :] = 20
    left, top, width, height = box
    # A low frequency patch: it must survive the 1920 -> 1280 -> 1920 resampling round trip
    # that anchors.check_template performs, so pure per-pixel noise would not do.
    rng = np.random.default_rng(7)
    coarse = Image.fromarray(rng.integers(40, 255, size=(4, 8, 3), dtype=np.uint8))
    patch = np.asarray(coarse.resize((width, height), Image.BICUBIC))
    image[top:top + height, left:left + width] = patch
    png = directory / ('%s.png' % name)
    Image.fromarray(image[:, :, ::-1]).save(png)
    digest = hashlib.sha256(png.read_bytes()).hexdigest()
    (directory / ('%s.json' % name)).write_text(json.dumps(
        {'image_sha256': digest, 'size': [size[0], size[1]], 'scene': 'BATTLE_HUD'}),
        encoding='utf-8')
    return png, digest


def write_registry(path, *, page_ids=('battle_hud', 'mirror_entry')):
    payload = {'version': 1, 'reference_width': 1280, 'reference_height': 720,
               'note': 'test registry',
               'pages': [{'id': page_id, 'title': page_id, 'evidence': [],
                          'identity': [{'id': '%s.label' % page_id, 'kind': 'ocr',
                                        'pattern': '^.+' , 'roi': [0.0, 0.0, 1.0, 1.0],
                                        'threshold': 0.65}],
                          'controls': [], 'live_derived': []}
                         for page_id in page_ids],
               'pending': []}
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return payload


def run(tmp_path, frame, extra=()):
    registry = tmp_path / 'anchors.json'
    if not registry.exists():
        write_registry(registry)
    argv = ['--label', 'battle.start_label', '--from', str(frame),
            '--box', '1518,738,60,28', '--page', 'battle_hud',
            '--registry', str(registry), '--template-root', str(tmp_path / 'base'),
            '--report', str(tmp_path / 'capture.json')]
    argv.extend(extra)
    return capture_anchors.main(argv), registry


def test_a_template_capture_lands_on_the_1280_baseline(tmp_path):
    frame, digest = write_frame(tmp_path)
    status, registry = run(tmp_path, frame, ['--image-dir', 'image/battle'])
    assert status == 0
    template = tmp_path / 'base' / 'image' / 'battle' / 'start_label.png'
    assert template.exists()
    with Image.open(template) as captured:
        assert captured.size == (40, 19)  # 60x28 on a 1920 frame scaled to the 1280 baseline
    payload = json.loads(registry.read_text(encoding='utf-8'))
    entry = payload['pages'][0]['controls'][0]
    assert entry['kind'] == 'template'
    assert entry['template'] == 'image/battle/start_label.png'
    assert entry['box'] == [1518, 738, 60, 28]
    # the roi is the center-normalized box, padded by at most one pixel on the far edges so
    # that anchors._pixels() truncation still covers the template (5 decimal rounding adds
    # at most another pixel)
    assert entry['roi'][0] * 1920 == pytest.approx(1518, abs=2)
    assert entry['roi'][1] * 1080 == pytest.approx(738, abs=2)
    assert entry['roi'][2] * 1920 == pytest.approx(1578, abs=2)
    assert entry['roi'][3] * 1080 == pytest.approx(766, abs=2)
    assert entry['threshold'] == 0.8
    assert 'captured from' in entry['note']
    report = json.loads((tmp_path / 'capture.json').read_text(encoding='utf-8'))
    assert report['check']['hit'] is True
    assert report['journal_sha256'] == digest
    assert report['frame_sha256'] == digest


def test_the_captured_template_is_replayed_against_its_own_frame(tmp_path):
    frame, _ = write_frame(tmp_path)
    status, registry = run(tmp_path, frame, ['--image-dir', 'image/battle'])
    assert status == 0
    payload = json.loads(registry.read_text(encoding='utf-8'))
    entry = payload['pages'][0]['controls'][0]
    checked = anchor_module.check_template(entry, str(frame), (1920, 1080), 1280, str(tmp_path / 'base'))
    assert checked['hit'] is True
    # the 40x19 baseline template is scaled back up by frame_width/reference_width, so the
    # observed box lands exactly on the captured region
    assert checked['observed']['box'] == [1518, 738, 60, 28]


def test_an_already_registered_anchor_is_refused_without_force(tmp_path):
    frame, _ = write_frame(tmp_path)
    status, registry = run(tmp_path, frame, ['--image-dir', 'image/battle'])
    assert status == 0
    before = registry.read_text(encoding='utf-8')
    with pytest.raises(SystemExit) as error:
        run(tmp_path, frame, ['--image-dir', 'image/battle'])
    assert 'already registered' in str(error.value)
    assert registry.read_text(encoding='utf-8') == before


def test_force_replaces_instead_of_appending(tmp_path):
    frame, _ = write_frame(tmp_path)
    run(tmp_path, frame, ['--image-dir', 'image/battle'])
    status, registry = run(tmp_path, frame, ['--image-dir', 'image/battle', '--force'])
    assert status == 0
    payload = json.loads(registry.read_text(encoding='utf-8'))
    controls = payload['pages'][0]['controls']
    assert len(controls) == 1
    report = json.loads((tmp_path / 'capture.json').read_text(encoding='utf-8'))
    assert report['replaced'] is True


def test_a_dry_run_writes_nothing(tmp_path):
    frame, _ = write_frame(tmp_path)
    status, registry = run(tmp_path, frame, ['--image-dir', 'image/battle', '--dry-run'])
    assert status == 0
    payload = json.loads(registry.read_text(encoding='utf-8'))
    assert payload['pages'][0]['controls'] == []
    assert not (tmp_path / 'base' / 'image' / 'battle' / 'start_label.png').exists()
    report = json.loads((tmp_path / 'capture.json').read_text(encoding='utf-8'))
    assert report['written'] is False


def test_a_geometry_capture_is_only_proven_on_its_own_frame(tmp_path):
    frame, digest = write_frame(tmp_path)
    registry = tmp_path / 'anchors.json'
    write_registry(registry)
    status = capture_anchors.main([
        '--label', 'entry.enter_button', '--kind', 'geometry',
        '--from', str(frame), '--box', '1056,447,168,60', '--page', 'mirror_entry',
        '--registry', str(registry), '--template-root', str(tmp_path / 'base'),
        '--report', str(tmp_path / 'capture.json'), '--note', 'dim while no run is pending'])
    assert status == 0
    payload = json.loads(registry.read_text(encoding='utf-8'))
    entry = [page for page in payload['pages'] if page['id'] == 'mirror_entry'][0]['controls'][0]
    assert entry['kind'] == 'geometry'
    assert entry['verified_on']['sha256'] == digest
    assert entry['verified_on']['box'] == [1056, 447, 168, 60]
    assert entry['verified_on']['source'] == 'dim while no run is pending'
    assert anchor_module.check_geometry(entry, {'image_sha256': digest})['hit'] is True
    stale = anchor_module.check_geometry(entry, {'image_sha256': 'ff' * 32})
    assert stale['hit'] is False and stale['stale'] is True


def test_an_unknown_page_is_refused(tmp_path):
    frame, _ = write_frame(tmp_path)
    registry = tmp_path / 'anchors.json'
    write_registry(registry)
    with pytest.raises(SystemExit) as error:
        capture_anchors.main([
            '--label', 'x.y', '--from', str(frame), '--box', '0,0,10,10', '--page', 'nope',
            '--registry', str(registry), '--template-root', str(tmp_path / 'base'),
            '--report', str(tmp_path / 'capture.json')])
    assert 'is not in the registry' in str(error.value)


def test_a_box_outside_the_frame_is_refused(tmp_path):
    frame, _ = write_frame(tmp_path)
    registry = tmp_path / 'anchors.json'
    write_registry(registry)
    with pytest.raises(SystemExit) as error:
        capture_anchors.main([
            '--label', 'battle.start_label', '--from', str(frame), '--box', '1900,1000,60,28',
            '--page', 'battle_hud', '--registry', str(registry),
            '--template-root', str(tmp_path / 'base'), '--report', str(tmp_path / 'capture.json')])
    assert 'does not fit' in str(error.value)
