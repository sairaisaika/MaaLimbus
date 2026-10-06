"""Replay the base-pipeline MapObserve node over retained frames; zero input."""
import argparse
import json
import time
from pathlib import Path

import cv2
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from verify_map_replay import Replay
from verify_theme_replay import ROOT, Journal, LimbusRecognition, LimbusTerminal, wait_job, wait_task

NODES = {'MapObserve': {'post_delay': 50}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--map-frame', required=True)
    parser.add_argument('--pack-frame', required=True)
    args = parser.parse_args()
    Library.open(args.binary, agent_server=False)
    Toolkit.init_option(ROOT / 'build/map-observe-debug')
    results = []
    for case, path in (('map', args.map_frame), ('pack_page_negative', args.pack_frame)):
        frame = cv2.imread(path)
        assert frame is not None, path
        evidence = ROOT / f'evidence/runtime/map-observe-replay-{time.time_ns()}-{case}'
        journal = Journal(evidence)
        recognition = LimbusRecognition('en', journal)
        controller = Replay(frame)
        resource = Resource()
        resource.register_custom_recognition('limbus_scene', recognition)
        resource.register_custom_action('limbus_terminal', LimbusTerminal(recognition))
        from recognition import MapObservation
        resource.register_custom_action('limbus_map_observe', MapObservation(recognition))
        for layer in ('base', 'en'):
            wait_job(resource.post_bundle(ROOT / f'assets/resource/{layer}'), timeout=20)
        wait_job(controller.post_connection())
        tasker = Tasker()
        assert tasker.bind(resource=resource, controller=controller)
        try:
            result = wait_task(tasker, tasker.post_task('MapObserve', NODES), deadline=time.monotonic() + 20)
        except RuntimeError:
            result = {'task_succeeded': False, 'stop_confirmed': True, 'timed_out': False}
        assert result['stop_confirmed'] and not result.get('timed_out'), (case, result)
        assert controller.input_attempts == [], controller.input_attempts
        events = [json.loads(line) for line in
                  (evidence / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        observed = next((e for e in events if e['event'] == 'map_observed'), None)
        results.append(dict(case=case, source=path, task_succeeded=result['task_succeeded'],
                            scene=None if observed is None else observed['scene'],
                            floor=None if observed is None else observed['floor'],
                            pack=None if observed is None else observed['pack'],
                            route=None if observed is None else observed['route'],
                            input_sent=False, evidence=str(evidence)))
    passed = (results[0]['scene'] == 'MAP' and results[0]['task_succeeded']
              and results[0]['floor'] == 1 and results[0]['route']['next_node'] is None
              and results[1]['scene'] != 'MAP' and not results[1]['task_succeeded'])
    output = ROOT / 'build/map-observe-replay-verification.json'
    output.write_text(json.dumps(dict(passed=passed, cases=results,
        scope='Actual Maa OCR executing the base pipeline MapObserve node on retained frames; no device, no input'),
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(output.read_text(encoding='utf-8'))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
