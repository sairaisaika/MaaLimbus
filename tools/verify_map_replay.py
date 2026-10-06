"""Actual Maa OCR/recognition over a retained map frame; no device or game input."""
import argparse
import json
import time
from pathlib import Path

import cv2
from maa.controller import CustomController
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from verify_theme_replay import ROOT, Journal, LimbusRecognition, LimbusTerminal, wait_job, wait_task

PIPELINE = {
    'OfflineMapHeader': {
        'recognition': 'Custom', 'custom_recognition': 'limbus_scene',
        'custom_recognition_param': {'scene': 'MAP'},
        'action': 'DoNothing', 'max_hit': 1, 'next': [], 'on_error': ['OfflineUnidentified'],
    },
    'OfflineUnidentified': {
        'recognition': 'DirectHit', 'action': 'Custom', 'custom_action': 'limbus_terminal',
        'custom_action_param': {'reason': 'retained_frame_is_not_an_identified_map_page'},
        'next': [], 'on_error': [],
    },
}


class Replay(CustomController):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame
        self.input_attempts = []

    def connect(self):
        return True

    def request_uuid(self):
        return 'retained-map-no-device'

    def get_features(self):
        return 0

    def screencap(self):
        return self.frame.copy()

    def _forbidden(self, name):
        self.input_attempts.append(name)
        raise AssertionError('Retained map replay must never send input: ' + name)

    def click(self, x, y):
        self._forbidden('click')

    def swipe(self, x1, y1, x2, y2, duration):
        self._forbidden('swipe')

    def touch_down(self, contact, x, y, pressure):
        self._forbidden('touch_down')

    def touch_move(self, contact, x, y, pressure):
        self._forbidden('touch_move')

    def touch_up(self, contact):
        self._forbidden('touch_up')

    def key(self, keycode):
        self._forbidden('key')


def directory():
    root = Path(__file__).resolve().parents[1] / 'build/map-replay-debug'
    (root / 'pipeline').mkdir(parents=True, exist_ok=True)
    (root / 'pipeline/map.json').write_text(json.dumps(PIPELINE, indent=2) + '\n', encoding='utf-8')
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--map-frame', required=True)
    parser.add_argument('--pack-frame', required=True)
    args = parser.parse_args()
    Library.open(args.binary, agent_server=False)
    Toolkit.init_option(directory())
    results = []
    for case, path in (('map', args.map_frame), ('pack_page_negative', args.pack_frame)):
        frame = cv2.imread(path)
        assert frame is not None, path
        directory_evidence = ROOT / f'evidence/runtime/map-replay-{time.time_ns()}-{case}'
        journal = Journal(directory_evidence)
        rec = LimbusRecognition('en', journal)
        controller = Replay(frame)
        resource = Resource()
        resource.register_custom_recognition('limbus_scene', rec)
        resource.register_custom_action('limbus_terminal', LimbusTerminal(rec))
        for layer in ('base', 'en'):
            wait_job(resource.post_bundle(ROOT / f'assets/resource/{layer}'), timeout=20)
        wait_job(resource.post_bundle(directory()), timeout=20)
        wait_job(controller.post_connection())
        tasker = Tasker()
        assert tasker.bind(resource=resource, controller=controller)
        result = wait_task(tasker, tasker.post_task('OfflineMapHeader'), deadline=time.monotonic() + 30)
        assert result['stop_confirmed'] and not result['timed_out'], (case, result)
        assert controller.input_attempts == [], controller.input_attempts
        events = [json.loads(line) for line in
                  (directory_evidence / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        frames = [json.loads(path.read_text(encoding='utf-8'))
                  for path in sorted(directory_evidence.glob('frame-*.json'))]
        assert frames, case
        scenes = sorted({f['scene'] for f in frames})
        recognized = [e for e in events if e['event'] == 'recognized']
        results.append(dict(case=case, source=path, frame_sha256=frames[0]['image_sha256'],
                            scenes=scenes, node_hits=[e['node'] for e in recognized],
                            device_input=False, evidence=str(directory_evidence)))
    passed = (results[0]['scenes'] == ['MAP'] and results[0]['node_hits'] == ['OfflineMapHeader']
              and 'MAP' not in results[1]['scenes'] and results[1]['node_hits'] == [])
    output = ROOT / 'build/map-frame-replay-verification.json'
    output.write_text(json.dumps(dict(passed=passed, cases=results,
        scope='Actual Maa OCR and scene classification on retained frames; no device, no node identity and no route input'),
        indent=2) + '\n', encoding='utf-8')
    print(output.read_text(encoding='utf-8'))
    assert passed


if __name__ == '__main__':
    main()
