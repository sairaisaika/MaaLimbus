"""Does a controller request survive the task that bound it ending?

D84's door asks `tasker.running`, and the live run that motivated it had reads that
worked right up to the click MaaFW answered `controller not found [controller_id=""]`.
That leaves one question the journals cannot answer: does the *controller* keep serving
requests after its task ends, or is the whole route released?

This probe sends no input.  It connects with the Null input method, asks for one
screenshot, runs a task that binds the controller and ends on its own, then asks for
another screenshot, and reports both answers plus the controller id around the task.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'agent'))

from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker

from maalimbus.adb_device import build, discover
from maalimbus.controller_lease import ControllerLease
from maalimbus.jobs import wait_job, wait_task
from recognition import Journal, LimbusRecognition

PIPELINE_DIR = ROOT / 'build/probe-route'
PIPELINE = {
    'RouteBinder': {
        'recognition': 'Custom',
        'custom_recognition': 'limbus_scene',
        'custom_recognition_param': {'scene': 'MAP'},
        'action': 'DoNothing',
        'max_hit': 1,
        'next': [],
        'on_error': [],
    },
    'RouteBinderAny': {
        'recognition': 'DirectHit',
        'action': 'DoNothing',
        'max_hit': 1,
        'next': [],
        'on_error': [],
    },
}


def prepare() -> Path:
    (PIPELINE_DIR / 'pipeline').mkdir(parents=True, exist_ok=True)
    (PIPELINE_DIR / 'pipeline/probe-route.json').write_text(
        json.dumps(PIPELINE, indent=2) + '\n', encoding='utf-8')
    return PIPELINE_DIR


def shot(controller, deadline):
    """One controller request.  Returns (ok, error, seconds)."""
    started = time.monotonic()
    try:
        wait_job(controller.post_screencap(), timeout=10, deadline=deadline)
        image = controller.cached_image
        return image is not None and bool(image.size), None, round(time.monotonic() - started, 2)
    except Exception as error:  # noqa: BLE001 - the probe reports, never raises
        return False, str(error)[:200], round(time.monotonic() - started, 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--adb', type=Path, default=None)
    parser.add_argument('--address', required=True)
    parser.add_argument('--node', default='RouteBinderAny')
    args = parser.parse_args()
    directory = ROOT / ('evidence/runtime/probe-route-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(parents=True)
    lease = ControllerLease.acquire(ROOT / 'build/controller.lock')
    deadline = time.monotonic() + 120
    result = dict(pid=os.getpid(), address=args.address, node=args.node,
                  input_sent=False, id_before=None, id_after=None, steps={})
    try:
        Library.open(args.binary, agent_server=False)
        device = discover(args.address, args.adb)
        result['device'] = device
        controller = build(device, input_enabled=False)
        wait_job(controller.post_connection(), timeout=15, deadline=deadline)
        result['id_before'] = getattr(controller, 'id', None)
        result['steps']['before_task'] = shot(controller, deadline)
        journal = Journal(directory)
        recognition = LimbusRecognition('en', journal)
        resource = Resource()
        resource.register_custom_recognition('limbus_scene', recognition)
        for layer in ('base', 'en'):
            wait_job(resource.post_bundle(ROOT / f'assets/resource/{layer}'),
                     timeout=20, deadline=deadline)
        wait_job(resource.post_bundle(prepare()), timeout=20, deadline=deadline)
        tasker = Tasker()
        assert tasker.bind(resource=resource, controller=controller)
        job = tasker.post_task(args.node)
        task = wait_task(tasker, job, deadline=time.monotonic() + 40)
        result['steps']['task'] = task
        result['id_after'] = getattr(controller, 'id', None)
        result['steps']['after_task'] = shot(controller, deadline)
        result['steps']['after_task_second'] = shot(controller, deadline)
        result['tasker_running_after'] = bool(getattr(tasker, 'running', False))
        result['controller_counts'] = getattr(controller, 'count', None)
        return 0
    finally:
        (directory / 'probe.json').write_text(
            json.dumps(result, indent=2, default=str) + '\n', encoding='utf-8')
        lease.close()
        print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    raise SystemExit(main())
