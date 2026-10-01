"""Production Maa graph, OCR and recognizer; saved frames only, never Win32 input."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np
from maa.controller import CustomController
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'agent')]
from recognition import Journal, LimbusRecognition, LimbusTerminal


class Replay(CustomController):
    def __init__(self, frames):
        super().__init__()
        self.frames, self.position, self.clicks = frames, 0, []

    def connect(self): return True
    def request_uuid(self): return 'maalimbus-offline-no-game'
    def get_features(self): return 0
    def screencap(self): return self.frames[self.position].copy()
    def click(self, x, y):
        self.clicks.append([x, y])
        frame = self.frames[self.position]
        h, w = frame.shape[:2]
        if self.position == 0:
            assert .23 * w < x < .46 * w and .25 * h < y < .55 * h
        elif self.position == 1:
            assert .76 * w < x < .97 * w and .55 * h < y < .85 * h
        else:
            raise AssertionError('No input allowed after team-selection boundary')
        self.position += 1
        return True
    def touch_down(self, *args): raise AssertionError('Unexpected touch')
    def touch_up(self, *args): raise AssertionError('Unexpected touch')


def redact(frame, kind, prepared=False):
    # Retained Maa frames have already been normalized. Upscaling then asking Maa
    # to downscale them again loses small outlined text; keep their exact pixels.
    frame = frame.copy() if prepared else cv2.resize(frame, (1920, round(frame.shape[0] * 1920 / frame.shape[1])))
    # Only public menu labels are fixtures; account identifiers/balances stay private.
    if kind in ('drive', 'team'):
        frame[int(.81 * frame.shape[0]):] = 0
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--references', type=Path, required=True)
    parser.add_argument('--prepared-frames',action='store_true',help='Retained normalized Maa frames; avoid a second resample')
    args = parser.parse_args()
    Library.open(args.binary, agent_server=False)
    Toolkit.init_option(ROOT / 'build/replay-debug')
    frames = [redact(cv2.imread(str(args.references / filename)), kind,args.prepared_frames) for filename, kind in
              [('image-3.png', 'drive'), ('image-4.png', 'entry'), ('image-2.png', 'team')]]
    results = []
    for name in ('references', 'changed_cover', 'unknown'):
        current = [f.copy() for f in frames]
        if name == 'changed_cover':
            h, w = current[1].shape[:2]
            current[1][int(.05*h):int(.95*h), int(.34*w):int(.65*w)] = (30, 150, 45)
        if name == 'unknown':
            current = [np.zeros_like(current[0])]
        directory = ROOT / f'evidence/runtime/replay-{name}'
        journal = Journal(directory)
        recognizer = LimbusRecognition('en', journal)
        resource, controller = Resource(), Replay(current)
        resource.register_custom_recognition('limbus_scene', recognizer)
        resource.register_custom_action('limbus_terminal', LimbusTerminal(recognizer))
        assert resource.post_bundle(ROOT / 'assets/resource/base').wait().succeeded
        assert resource.post_bundle(ROOT / 'assets/resource/en').wait().succeeded
        assert controller.post_connection().wait().succeeded
        tasker = Tasker()
        assert tasker.bind(resource=resource, controller=controller)
        override = {k: {'timeout': 1500, 'post_delay': 50} for k in ['MirrorHard', 'MirrorDrive', 'MirrorEnter']}
        override['MirrorHard']['action']='DoNothing' # Saved-frame controller: bypass only OS preflight.
        job = tasker.post_task('MirrorHard', override)
        deadline = time.monotonic() + 15
        while not job.done and time.monotonic() < deadline:
            time.sleep(.1)
        if not job.done:
            tasker.post_stop().wait()
            raise AssertionError('Replay exceeded bounded timeout')
        assert len(controller.clicks) == (0 if name == 'unknown' else 2), (name, controller.clicks, recognizer.last_scene)
        assert recognizer.last_scene == ('UNKNOWN' if name == 'unknown' else 'TEAM_LIBRARY')
        results.append({'case': name, 'clicks': controller.clicks, 'last_scene': recognizer.last_scene})
    output = ROOT / 'build/native-replay-verification.json'
    output.write_text(json.dumps({'passed': True, 'device_controller': False, 'cases': results,
                                  'scope': 'Scripted reference sequence: Drive and Enter clicks; unrelated library frame is correctly refused as dungeon deployment. No live transition or five-floor assertion.'}, indent=2), encoding='utf-8')
    print(output.read_text(encoding='utf-8'))


if __name__ == '__main__':
    main()
