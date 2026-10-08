"""The extracted window loop, driven offline.

`tools/window_step.py` was the only code that played a full Mirror Dungeon run, and
that made the loop untestable: driving it meant a device. The loop now lives in
`maalimbus.runner`, and the two things it needs are injected -- the page arrives from
an observer, the input leaves through a device -- so these cases drive the real loop
over frames the live tools already recorded under `evidence/runtime/**`.

What is checked here is the seam the extraction had to preserve, not the planner (that
is `tests/test_window.py`):

  * one `step()` on an archived page reads the same page, plans the same single input,
    sends it through the injected device and records the same evidence frames;
  * a page that never becomes readable is waited out and then stops the run with the
    reason the CLI has always printed;
  * `MaaDevice` maps `screencap`/`click`/`swipe`/`key` onto the controller the agent
    owns, including the screenshot scale the recognition space depends on;
  * the runner reaches for neither the Maa framework nor the agent package, which is
    what makes it importable from an agent custom action and from a test.
"""
import ast
import json
import sys
from pathlib import Path

import cv2
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.runner import (FakeDevice, FrameObserver, MaaDevice,  # noqa: E402
                              MirrorRunner, REGISTRY)

# A live window whose first pages are the run summary's claim: frame-0001 is RUN_CLAIM,
# and the plan's one input is the Claim button the anchors prove at [1638, 855, 180, 80].
CLAIM_DIR = ROOT / 'evidence/runtime/window-20261007-021150'
CLAIM_FRAME = CLAIM_DIR / 'frame-0001.json'
CLAIM_SUCCESSOR = CLAIM_DIR / 'frame-0002.json'
CLAIM_BOX = [1638, 855, 180, 80]
CLAIM_REASON = 'claiming_is_the_only_forward_input_on_the_run_summary'

# frame-0002 of this window is a transition: the recognition layer names it UNKNOWN and
# no anchor claims it, so it is a page to wait out rather than one to act on.
UNREADABLE_FRAME = ROOT / 'evidence/runtime/window-20261006-025801/frame-0002.json'


def archived(path):
    """The frame's image, read the way a device would hand it over."""
    image = cv2.imread(str(Path(path).with_suffix('.png')))
    assert image is not None, path
    return image


def window(tmp_path, frames, settings):
    """A runner over archived frames, with an in-memory device for its input.

    ``frames`` is the exact sequence the device will hand out, so a case names both
    the page the loop reads and the pages it settles on.
    """
    device = FakeDevice([archived(frame) for frame in frames])
    observer = FrameObserver(tmp_path, [str(frame) for frame in frames])
    runner = MirrorRunner(device, settings=settings, registry=json.loads(
        REGISTRY.read_text(encoding='utf-8')), directory=tmp_path, observer=observer)
    return runner, device


def test_one_step_reads_the_archived_page_and_sends_its_planned_click(tmp_path):
    runner, device = window(tmp_path, [CLAIM_FRAME, CLAIM_SUCCESSOR], {'rounds': 1})
    result = runner.step()

    assert result['page'] == 'RUN_CLAIM'
    assert result['reason'] == CLAIM_REASON
    assert list(result['target']) == CLAIM_BOX
    assert result['input_sent'] is True
    assert result['event'] == 'window_intent'
    assert result['stopped'] is None
    assert result['done'] is False
    # The observation is the record the CLI writes into its frame JSON, unchanged.
    assert result['observation']['scene'] == 'RUN_CLAIM'
    assert result['observation']['ocr']

    # Exactly one input, and it landed inside the box the plan named.
    assert len(device.clicks) == 1
    x, y = device.clicks[0]
    assert CLAIM_BOX[0] <= x <= CLAIM_BOX[0] + CLAIM_BOX[2]
    assert CLAIM_BOX[1] <= y <= CLAIM_BOX[1] + CLAIM_BOX[3]
    assert device.swipes == [] and device.keys == []

    # The step kept the CLI's evidence: the page it read and the one it settled on.
    frames = sorted(path.name for path in tmp_path.glob('frame-*.json'))
    assert len(frames) == 2, frames
    first = json.loads((tmp_path / frames[0]).read_text(encoding='utf-8'))
    assert first['scene'] == 'RUN_CLAIM'
    assert first['image_sha256'] == json.loads(
        CLAIM_FRAME.read_text(encoding='utf-8'))['image_sha256']


def test_a_run_over_the_claim_pages_sends_one_click_per_step(tmp_path):
    frames = [CLAIM_DIR / f'frame-000{copy}.json' for copy in (1, 2, 3, 4)]
    runner, device = window(tmp_path, frames, {'rounds': 1})
    result = runner.run(steps=2, interval=0.0, round_limit=2)

    assert result['passed'] is True
    assert result['reason'] == 'window_steps_passed'
    assert result['clicks_sent'] == 2
    assert [entry['page_before'] for entry in result['steps']] == ['RUN_CLAIM'] * 2
    assert [entry['passed'] for entry in result['steps']] == [True, True]
    assert len(device.clicks) == 2


def test_a_run_waits_out_an_unreadable_page_and_then_stops(tmp_path):
    runner, device = window(tmp_path, [UNREADABLE_FRAME] * 6,
                            {'rounds': 1, 'unknown_rounds': 2})
    result = runner.run(steps=5, interval=0.0, round_limit=5)

    assert result['passed'] is False
    assert result['reason'] == 'page_unreadable_after_waiting'
    # Nothing was clicked at a page the run could not read.
    assert result['clicks_sent'] == 0
    assert device.clicks == []
    assert [entry['stopped'] for entry in result['steps']] == \
        ['page_unreadable_after_waiting']


class StubController:
    """The controller the agent's task owns, reduced to what :class:`MaaDevice` calls."""

    def __init__(self):
        self.calls = []
        self.cached_image = object()

    def set_screenshot_target_long_side(self, value):
        self.calls.append(('target_long_side', value))

    def post_screencap(self):
        self.calls.append(('post_screencap',))
        return 'screencap-job'

    def post_click(self, x, y):
        self.calls.append(('post_click', x, y))
        return 'click-job'

    def post_swipe(self, x1, y1, x2, y2, duration_ms):
        self.calls.append(('post_swipe', x1, y1, x2, y2, duration_ms))
        return 'swipe-job'


def test_maa_device_maps_the_loop_onto_the_controller_it_was_given():
    controller = StubController()
    waited = []
    device = MaaDevice(controller, wait=lambda job, timeout=None, deadline=None:
                       waited.append((job, timeout)))

    # The recognition space is 1920 wide, so the controller is told to scale to it
    # before any screencap is asked for.
    assert controller.calls == [('target_long_side', 1920)]

    assert device.screencap() is controller.cached_image
    assert ('post_screencap',) in controller.calls

    device.click(11, 22)
    device.swipe(1, 2, 3, 4, 500)
    assert ('post_click', 11, 22) in controller.calls
    assert ('post_swipe', 1, 2, 3, 4, 500) in controller.calls
    # Every input is waited out, and a drag keeps the window's own longer timeout.
    assert ('click-job', 10) in waited
    assert ('swipe-job', 15) in waited

    # A controller with no key input says so instead of silently dropping the key.
    with pytest.raises(NotImplementedError):
        device.key(4)


def test_maa_device_applies_the_scale_it_was_asked_for():
    controller = StubController()
    MaaDevice(controller, wait=lambda job, **kwargs: job, target_long_side=1280)
    assert controller.calls == [('target_long_side', 1280)]

    other = StubController()
    MaaDevice(other, wait=lambda job, **kwargs: job, target_long_side=None)
    assert other.calls == []


def test_the_runner_reaches_for_neither_the_framework_nor_the_agent():
    """The loop must import on its own: that is what lets an agent action reuse it."""
    imports = set()
    for node in ast.walk(ast.parse((ROOT / 'src/maalimbus/runner.py')
                                   .read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split('.')[0])
    assert 'maa' not in imports
    assert 'recognition' not in imports


@pytest.mark.parametrize('page',['RUN_REWARD_DIALOG','RUN_REWARD_CONFIRM','RUN_REWARD_BONUS'])
def test_paid_reward_controls_stop_with_missing_module_budget(tmp_path,monkeypatch,page):
    import maalimbus.runner as module
    runner,device=window(tmp_path,[CLAIM_FRAME],{'rounds':1})
    monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.setattr(module,'resolve_scene',lambda *args:page)
    result=runner.step()
    assert result['stopped']=='reward_module_budget_pending'
    assert result['done'] and not result['input_sent']
    assert device.clicks==[] and device.swipes==[]


def test_battle_submission_intent_survives_device_failure(tmp_path,monkeypatch):
    from maalimbus.storage import ProfileStore,SINNERS
    from maalimbus.policies import Team
    from maalimbus.deployment_transaction import DeploymentTransaction
    order=[3,4,9,1,7,2,12,5,8,10,11,6]
    ProfileStore(tmp_path/'user-team-profiles.json').save([Team(2,frozenset({'Charge','Tremor'}),
        deployment=tuple(SINNERS[n-1] for n in order))])
    installed = tmp_path/'installed-config'
    installed.mkdir()
    (installed/'user-data-root.json').write_text(json.dumps({'version':1,'directory':str(tmp_path)}))
    monkeypatch.setenv('MAALIMBUS_DATA_PATH',str(installed))
    frame=ROOT/'evidence/runtime/window-20261008-045214/frame-0008.json'
    runner,device=window(tmp_path,[frame],{'team':2,'rounds':1})
    runner.run_id='test';t=DeploymentTransaction(tmp_path/'deployment.json')
    t.prepare('test',order,(0,12))
    for i,card in enumerate(order):t.intent('card',(i,12),card);t.observe((i+1,12))
    runner.deployment_transaction=t
    def fail_click(*args):
        assert DeploymentTransaction(t.path).data['submit_pending'] is True
        raise RuntimeError('simulated controller disconnect')
    monkeypatch.setattr(device,'click',fail_click)
    with pytest.raises(RuntimeError,match='simulated controller disconnect'):runner.step()
    with pytest.raises(ValueError):DeploymentTransaction(t.path).prepare('test',order,(12,12))


def test_stop_page_prevents_the_first_input_on_that_page(tmp_path):
    runner,device=window(tmp_path,[CLAIM_FRAME],{'stop_page':'RUN_CLAIM'})
    result=runner.step()
    assert result['done'] and result['stopped']=='stop_page_reached'
    assert not result['input_sent'] and device.clicks==[]
