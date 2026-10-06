"""Cross-validate the map scene on a live MuMu capture against the retained frame."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from verify_map_replay import PIPELINE, Replay, directory
from verify_theme_replay import ROOT, Journal, LimbusRecognition, LimbusTerminal, wait_job, wait_task


def observe(binary, image, label):
    Library.open(binary, agent_server=False)
    Toolkit.init_option(directory())
    evidence = ROOT / f'evidence/runtime/map-crosscheck-{time.time_ns()}-{label}'
    journal = Journal(evidence)
    rec = LimbusRecognition('en', journal)
    controller = Replay(image)
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
    assert result['stop_confirmed'] and not result['timed_out'], (label, result)
    assert controller.input_attempts == [], controller.input_attempts
    frames = [json.loads(path.read_text(encoding='utf-8'))
              for path in sorted(evidence.glob('frame-*.json'))]
    assert len(frames) == 1, (label, len(frames))
    frame = frames[0]
    return dict(label=label, image_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
                scene=frame['scene'], size=frame['size'],
                ocr=[{'text': t['text'], 'score': t['score'], 'box': t['box']}
                     for t in frame['ocr']],
                evidence=str(evidence), input_sent=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--live-frame', required=True,
                        help='read-only capture taken from the running MuMu emulator')
    parser.add_argument('--retained-frame', required=True)
    args = parser.parse_args()

    live = cv2.imread(args.live_frame)
    retained = cv2.imread(args.retained_frame)
    assert live is not None and retained is not None
    live_result = observe(args.binary, live, 'live-mumu')
    retained_result = observe(args.binary, retained, 'retained-231221')

    def header(result):
        from maalimbus.map_vision import map_header
        from maalimbus.vision import Text
        records = [Text(t['text'], tuple(t['box']), t['score']) for t in result['ocr']]
        return map_header(records, tuple(result['size']))

    live_header, retained_header = header(live_result), header(retained_result)
    same_identity = (live_header is not None and retained_header is not None
                     and (live_header.floor, live_header.pack) ==
                         (retained_header.floor, retained_header.pack))
    live_text = {t['text'].strip() for t in live_result['ocr'] if t['text'].strip()}
    retained_text = {t['text'].strip() for t in retained_result['ocr'] if t['text'].strip()}
    report = {
        'passed': (live_result['scene'] == 'MAP' and retained_result['scene'] == 'MAP'
                   and same_identity
                   and 'Exploring Floor 1' in live_text and 'Exploring Floor 1' in retained_text
                   and 'To be Cleaved' in live_text and 'To be Cleaved' in retained_text),
        'live_mumu': {k: v for k, v in live_result.items() if k != 'ocr'},
        'retained_231221': {k: v for k, v in retained_result.items() if k != 'ocr'},
        'live_identity': None if live_header is None else
            {'floor': live_header.floor, 'pack': live_header.pack,
             'header_box': live_header.exploring_text.box, 'pack_box': live_header.pack_text.box},
        'retained_identity': None if retained_header is None else
            {'floor': retained_header.floor, 'pack': retained_header.pack,
             'header_box': retained_header.exploring_text.box, 'pack_box': retained_header.pack_text.box},
        'only_in_live': sorted(live_text - retained_text),
        'only_in_retained': sorted(retained_text - live_text),
        'device_input': False,
        'scope': ('Actual Maa OCR on a read-only MuMu capture compared with the retained 231221 '
                  'frame: scene identity only, zero controller input.'),
    }
    output = ROOT / 'build/map-live-crosscheck-verification.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('only_in_live', 'only_in_retained')},
                     ensure_ascii=False, indent=1))
    print('only in live:', report['only_in_live'])
    print('only in retained:', report['only_in_retained'])
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
