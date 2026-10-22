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
import shutil
import sys
from pathlib import Path

import cv2
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.runner import (FakeDevice, FrameObserver, MaaDevice,  # noqa: E402
                              MaaObserver, MirrorRunner, REGISTRY, candidates_of,
                              header_chrome, inside_chrome, observe, team_state)
import maalimbus.runner as runner_module  # noqa: E402

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


def _ledger(tmp_path, monkeypatch, completed):
    """A run ledger whose verified-run total is the number this case names."""
    from types import SimpleNamespace
    from maalimbus.storage import RunStore
    store = RunStore(tmp_path / 'user-run-ledger.json', [SimpleNamespace(slot=2)])
    scope = store.start()
    monkeypatch.setattr(runner_module, '_completed_runs', lambda ledger: completed)
    return store, scope


def test_a_named_run_count_is_delivered_only_by_a_verified_run(tmp_path, monkeypatch):
    """The count is the ledger's own verified total, not the step bound.

    ``completed_runs`` only advances on ``entry_returned``, which the ledger refuses
    before five verified floors, a victory and a claimed reward, so a run that was
    abandoned or expired can never satisfy the player's number.
    """
    store, scope = _ledger(tmp_path, monkeypatch, 1)
    runner = MirrorRunner(FakeDevice([]), settings={'rounds': 1, 'run_count': 2},
                          directory=tmp_path, store=store, run_id=scope)
    assert (runner.run_baseline, runner._verified_runs()) == (1, 0)
    assert runner._run_count_reached() is None
    monkeypatch.setattr(runner_module, '_completed_runs', lambda ledger: 2)
    assert (runner._verified_runs(), runner._run_count_reached()) == (1, None)
    monkeypatch.setattr(runner_module, '_completed_runs', lambda ledger: 3)
    assert runner._run_count_reached() == dict(target=2, completed=2)


def test_no_named_run_count_never_stops_the_window(tmp_path, monkeypatch):
    store, scope = _ledger(tmp_path, monkeypatch, 4)
    runner = MirrorRunner(FakeDevice([]), settings={'rounds': 1},
                          directory=tmp_path, store=store, run_id=scope)
    assert runner.settings.run_count == 0 and runner._run_count_reached() is None


def test_the_window_hands_control_back_once_the_named_run_count_is_delivered(tmp_path,
                                                                             monkeypatch):
    """The delivered number stops the window in place and no further input goes out."""
    store, scope = _ledger(tmp_path, monkeypatch, 0)
    runner, device = window(tmp_path, [CLAIM_FRAME, CLAIM_SUCCESSOR],
                            {'rounds': 1, 'run_count': 1})
    runner.store, runner.run_id, runner.run_baseline = store, scope, 0
    monkeypatch.setattr(runner_module, '_completed_runs', lambda ledger: 1)
    result = runner.step()
    assert (result['reason'], result['stopped'], result['input_sent'], result['done']) == (
        'run_count_reached', 'run_count_reached', True, True)
    assert result['verified_runs'] == dict(target=1, completed=1)
    # This step's own click went out; the window then handed control back instead of
    # starting another run.
    assert len(device.clicks) == 1 and device.swipes == []
    assert runner.summary()['verified_runs'] == dict(target=1, completed=1,
                                                     ledger_total=1, counted_at_launch=0)


def test_observe_battle_preference_reaches_runner_and_sends_no_input(tmp_path):
    frame=ROOT/'evidence/runtime/battle-auto-assign-20261006-011029/frame-0001.json'
    instance,device=window(tmp_path,[frame],dict(rounds=1,interval=0,battle_assignment='observe'))
    result=instance.step()
    assert result['reason']=='battle_assignment_observe_only'
    assert not device.clicks and not device.swipes


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


def test_old_scoped_reward_budget_is_reported_as_pending(tmp_path,monkeypatch):
    import maalimbus.runner as module
    from maalimbus.storage import write_json
    runner,device=window(tmp_path,[CLAIM_FRAME],{'rounds':1})
    monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.setattr(module,'resolve_scene',lambda *args:'RUN_REWARD_DIALOG')
    write_json(tmp_path/'config/user-mirror-settings.json',dict(
        max_reward_modules=6,module_budget_pending=False,reward_budget_scope='old-run'))
    result=runner.step()
    assert result['stopped']=='reward_module_budget_pending'
    assert not result['input_sent'] and device.clicks==[]


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


class Notes:
    """The journal surface the runner uses, recording instead of writing a file."""

    def __init__(self):
        self.events=[]

    def record(self,event,**details):
        self.events.append((event,details))


def test_a_swallowed_click_is_retried_before_the_run_gives_up(tmp_path):
    # Live 2026-10-12: the packaged application sent the DUNGEON_TEAM slot click
    # through `adb shell input tap`, MaaFramework reported it as succeeded, and the
    # page never moved, so the run ended on its first step. The same page served five
    # times is what a swallowed tap looks like offline: identical pixels, identical
    # OCR, and a plan whose `advance` claimed something had to change.
    frames=[archived(CLAIM_FRAME) for _ in range(6)]
    device=FakeDevice(frames)
    observer=FrameObserver(tmp_path,[str(CLAIM_FRAME)]*6)
    notes=Notes()
    runner=MirrorRunner(device,settings={'rounds':1,'interval':0.0,'page_tries':2,
                                         'recovery_tries':0},
                        registry=json.loads(REGISTRY.read_text(encoding='utf-8')),
                        directory=tmp_path,observer=observer,journal=notes)
    result=runner.run(steps=4,interval=0.0,round_limit=4)

    # The click was retried once (page_tries) and only then did the run stop, so two
    # inputs went out instead of the single one the user's run managed.
    assert result['passed'] is False
    assert result['reason']=='unexpected_successor'
    assert result['clicks_sent']==2
    assert len(device.clicks)==2
    assert [entry['stopped'] for entry in result['steps']]==[
        'click_was_swallowed_by_the_game','unexpected_successor']
    assert [entry['passed'] for entry in result['steps']]==[False,False]
    # The retry is named with the installation's input posture, which is the fact the
    # person reading the log needs: a healthy framework line means look at the box.
    swallowed=[details for event,details in notes.events if event=='window_click_swallowed']
    assert len(swallowed)==1
    assert swallowed[0]['attempt']==1 and swallowed[0]['reason']==CLAIM_REASON
    assert swallowed[0]['input_helpers'].startswith('input helpers:')


# The live Grace page of 2026-10-12 01:50: frame-0001 reads every price once, and
# frame-0005 is the frame the device handed back right after a purchase re-rendered a
# price, where that price reads twice.
GRACE_DIR = ROOT / 'evidence/runtime/window-20261012-015054'
GRACE_CLEAN = GRACE_DIR / 'frame-0001.json'
GRACE_REREAD = GRACE_DIR / 'frame-0005.json'
GRACE_REASON = 'grace_card_is_bought_within_the_available_starlight'


def grace_window(tmp_path, frames, settings, monkeypatch, reading, notes=None):
    """A Grace-page runner whose counter reading is the case's own."""
    import maalimbus.runner as runner_module
    monkeypatch.setattr(runner_module, 'available_starlight', reading)
    device = FakeDevice([archived(frame) for frame in frames])
    observer = FrameObserver(tmp_path, [str(frame) for frame in frames])
    runner = MirrorRunner(device, settings=settings, registry=json.loads(
        REGISTRY.read_text(encoding='utf-8')), directory=tmp_path, observer=observer,
        journal=notes if notes is not None else Notes())
    return runner, device


def test_a_grace_page_that_reads_nothing_is_reread_before_the_run_gives_up(tmp_path,
                                                                         monkeypatch):
    # The counter and the prices are read from the newest frame on every round, so a
    # frame that proves nothing is a frame rather than a page: live 2026-10-12 01:50 the
    # run stopped on 'configured_grace_costs_not_proven' because the frame taken right
    # after a purchase carried one price twice. The run spends a bounded round re-reading
    # instead of ending there, and then buys exactly as it would have.
    if not GRACE_CLEAN.exists():
        pytest.skip('retained live grace-page evidence is not present')
    from maalimbus import runner as runner_module
    real = runner_module.available_starlight
    calls = []
    def flaky(records, size, **options):
        calls.append(1)
        return None if len(calls) == 1 else real(records, size, **options)
    runner, device = grace_window(tmp_path, [GRACE_CLEAN, GRACE_CLEAN, GRACE_REREAD,
                                             GRACE_REREAD],
                                  {'rounds': 1, 'interval': 0.0, 'page_tries': 2,
                                   'graces': '2', 'grace_budget': 100},
                                  monkeypatch, flaky)
    result = runner.run(steps=1, interval=0.0, round_limit=2)

    assert len(calls) == 2, 'the unreadable round must not spend the run'
    assert result['passed'] is True
    assert result['reason'] == 'window_steps_passed'
    assert result['clicks_sent'] == 1
    assert [entry['reason'] for entry in result['steps']] == [GRACE_REASON]


def test_a_grace_page_that_never_reads_still_stops_on_its_own_reason(tmp_path, monkeypatch):
    # page_tries bounds the wait, so a page that never reads stops with the reason the
    # log has always shown and no input is sent at a page the run could not read.
    if not GRACE_CLEAN.exists():
        pytest.skip('retained live grace-page evidence is not present')
    calls = []
    def unreadable(records, size, **options):
        calls.append(1)
        return None
    runner, device = grace_window(tmp_path, [GRACE_CLEAN] * 4,
                                  {'rounds': 1, 'interval': 0.0, 'page_tries': 2,
                                   'graces': '2'},
                                  monkeypatch, unreadable)
    result = runner.run(steps=2, interval=0.0, round_limit=4)

    assert len(calls) == 2
    assert result['passed'] is False
    assert result['reason'] == 'starlight_available_balance_not_proven'
    assert result['clicks_sent'] == 0
    assert device.clicks == []
    assert [entry['stopped'] for entry in result['steps']] == \
        ['starlight_available_balance_not_proven']


def test_a_configured_set_the_page_cannot_pay_for_narrows_and_leaves_the_page(tmp_path,
                                                                              monkeypatch):
    # The live 01:56 run bought 2,4,5 and then refused the Graces page forever, because
    # that page offered 60 starlight and the configured set costs 100. A wish list the
    # page cannot pay for narrows onto the prefix this run already paid for, so the run
    # reaches the page's own Enter instead of stopping on a count it can never satisfy.
    if not GRACE_CLEAN.exists():
        pytest.skip('retained live grace-page evidence is not present')
    from types import SimpleNamespace
    import maalimbus.runner as runner_module
    from maalimbus.storage import RunStore
    store = RunStore(tmp_path / 'user-run-ledger.json', [SimpleNamespace(slot=2)])
    scope = store.start()
    (tmp_path / 'user-grace-transaction.json').write_text(json.dumps(dict(
        scope=scope, requested=[2, 4, 5, 7], budget=100, selected=[2, 4, 5], spent=60,
        available=0, pending=None, proofs=['entry'])), encoding='utf-8')
    notes = Notes()
    device = FakeDevice([archived(GRACE_CLEAN) for _ in range(4)])
    observer = FrameObserver(tmp_path, [str(GRACE_CLEAN)] * 4)
    monkeypatch.setattr(runner_module, 'available_starlight', lambda records, size, **o: 0)
    runner = MirrorRunner(device, settings={'rounds': 1, 'interval': 0.0, 'page_tries': 2,
                                            'recovery_tries': 0,
                                            'graces': '2,4,5,7', 'grace_budget': 100},
                          registry=json.loads(REGISTRY.read_text(encoding='utf-8')),
                          directory=tmp_path, observer=observer, journal=notes,
                          store=store, run_id=scope)
    result = runner.run(steps=1, interval=0.0, round_limit=1)

    # The step is the page's own Enter: the run was stopped by the offline frame that
    # never moves, not by the count.
    assert result['clicks_sent'] == 1
    assert result['steps'][0]['plan']['reason'] == 'the_graces_page_is_left_with_its_own_enter'
    assert result['steps'][0]['stopped'] == 'unexpected_successor'
    assert runner.state['grace_wanted'] == [2, 4, 5]
    written = json.loads((tmp_path / 'user-grace-transaction.json').read_text(encoding='utf-8'))
    assert written['requested'] == [2, 4, 5]
    assert written['affordable_plan']['previous_requested'] == [2, 4, 5, 7]
    narrowed = [details for event, details in notes.events
                if event == 'grace_selection_narrowed_to_the_affordable_prefix']
    assert len(narrowed) == 1
    assert narrowed[0]['requested'] == [2, 4, 5, 7] and narrowed[0]['affordable'] == [2, 4, 5]
    assert narrowed[0]['unaffordable'] == [7]


# The floor theme pack is pulled down and the game answers with one empty frame before
# the map is drawn: frame-0020 of this window carries no text at all, while the next
# probe of the same device found the game already on MAP with the pulled pack on it.
THEME_DIR = ROOT / 'evidence/runtime/window-20261012-021508'
THEME_PAGE = THEME_DIR / 'frame-0019.json'
THEME_LOADING = THEME_DIR / 'frame-0020.json'
THEME_MAP = ROOT / 'evidence/runtime/window-20261012-022123/frame-0001.json'
THEME_REASON = 'the_floor_theme_pack_is_pulled_down_to_be_taken'


def test_the_theme_pull_waits_out_the_empty_frame_before_it_judges(tmp_path):
    # The live 02:17 run pulled the pack, read the empty loading frame two seconds later
    # and stopped with 'Selected theme successor map floor/name is not proven' — but the
    # pull had worked and the map was on its way. The step reads its successor on the
    # unknown budget and keeps waiting while the page it cannot name changes, so the
    # map the pull really earned is what proves it.
    for frame in (THEME_PAGE, THEME_LOADING, THEME_MAP):
        if not frame.exists():
            pytest.skip('retained live theme-page evidence is not present')
    import shutil
    from types import SimpleNamespace
    from maalimbus.storage import RunStore
    shutil.copyfile(ROOT / 'config/user-team-profiles.json',
                    tmp_path / 'user-team-profiles.json')
    store = RunStore(tmp_path / 'user-run-ledger.json', [SimpleNamespace(slot=2)])
    scope = store.start()
    frames = [THEME_PAGE, THEME_LOADING, THEME_LOADING, THEME_MAP, THEME_MAP, THEME_MAP]
    device = FakeDevice([archived(frame) for frame in frames])
    observer = FrameObserver(tmp_path, [str(frame) for frame in frames])
    notes = Notes()
    runner = MirrorRunner(device,
                          settings={'rounds': 1, 'unknown_rounds': 6, 'interval': 0.0,
                                    'page_tries': 2, 'grace_budget': 100},
                          registry=json.loads(REGISTRY.read_text(encoding='utf-8')),
                          directory=tmp_path, observer=observer, journal=notes,
                          store=store, run_id=scope)
    result = runner.run(steps=1, interval=0.0, round_limit=1)

    assert result['clicks_sent'] == 1
    assert result['steps'][0]['plan']['reason'] == THEME_REASON
    assert result['steps'][0]['page_after'] == 'MAP'
    assert result['passed'] is True and result['reason'] == 'window_steps_passed'
    written = json.loads((tmp_path / 'user-theme-transaction.json').read_text(encoding='utf-8'))
    assert written['pending'] is None
    assert [entry['floor'] for entry in written['selected']] == [1]
    assert written['selected'][0]['name'] == 'To be Cleaved'


def test_changed_pixels_on_named_theme_loading_are_not_a_successor(tmp_path):
    from types import SimpleNamespace
    from maalimbus.storage import RunStore
    for p in (THEME_PAGE,THEME_LOADING,THEME_MAP):
        if not p.exists():pytest.skip('Retained theme frames unavailable')
    loading=tmp_path/'named-loading.json'
    payload=json.loads(THEME_LOADING.read_text(encoding='utf-8'));payload['scene']='THEME_PACKS'
    loading.write_text(json.dumps(payload),encoding='utf-8')
    shutil.copyfile(THEME_LOADING.with_suffix('.png'),loading.with_suffix('.png'))
    shutil.copyfile(ROOT/'config/user-team-profiles.json',tmp_path/'user-team-profiles.json')
    store=RunStore(tmp_path/'user-run-ledger.json',[SimpleNamespace(slot=2)]);scope=store.start()
    frames=[THEME_PAGE,loading,THEME_MAP]
    instance=MirrorRunner(FakeDevice([archived(f) for f in frames]),
        settings=dict(rounds=1,unknown_rounds=3,interval=0),directory=tmp_path,
        observer=FrameObserver(tmp_path,list(map(str,frames))),store=store,run_id=scope,journal=Notes())
    result=instance.run(steps=1,interval=0,round_limit=1)
    assert result['passed'] and result['clicks_sent']==1
    assert len(instance.device.swipes)==1
    assert instance.theme_transaction.data['pending'] is None


# The pre-battle participant counter rolls up while it changes and one settled frame can
def test_theme_drag_waits_past_a_named_but_stale_previous_floor(tmp_path):
    from types import SimpleNamespace
    from maalimbus.storage import RunStore
    before=ROOT/'evidence/runtime/packaged-mirror-20261012-045906/frame-0008.json'
    stale=before.with_name('frame-0009.json')
    after=ROOT/'evidence/runtime/packaged-mirror-20261012-050948/frame-0001.json'
    assert all(p.exists() for p in (before,stale,after))
    shutil.copyfile(ROOT/'config/user-team-profiles.json',tmp_path/'user-team-profiles.json')
    store=RunStore(tmp_path/'user-run-ledger.json',[SimpleNamespace(slot=7)])
    scope=store.start()
    frames=[before,stale,after]
    device=FakeDevice([archived(f) for f in frames])
    notes=Notes()
    instance=MirrorRunner(device,settings=dict(rounds=1,unknown_rounds=3,interval=0),
        directory=tmp_path,observer=FrameObserver(tmp_path,list(map(str,frames))),
        registry=json.loads(REGISTRY.read_text(encoding='utf-8')),
        journal=notes,store=store,run_id=scope)
    result=instance.run(steps=1,interval=0,round_limit=1)
    assert result['passed'] and result['clicks_sent']==1
    assert len(device.swipes)==1 and not device.clicks
    assert any(event=='theme_successor_read_retry' for event,_ in notes.events)
    state=json.loads((tmp_path/'user-theme-transaction.json').read_text(encoding='utf-8'))
    assert state['pending'] is None
    assert state['selected'][0]['floor']==2
    assert state['selected'][0]['name']=='Emotional Indolence'


# The pre-battle participant counter rolls up while it changes and one settled frame can
# be read without it: frame-0026 of this window is a PRE_BATTLE_TEAM frame whose counter
# band carried only the 'Chai' label under it, while the frames either side read 7/12.
DEPLOY_DIR = ROOT / 'evidence/runtime/window-20261012-022454'
DEPLOY_NO_COUNTER = DEPLOY_DIR / 'frame-0026.json'


def test_a_pre_battle_frame_without_its_counter_is_reread(tmp_path):
    # The live 02:26 run stopped on 'Deployment successor participant count not proven'
    # after a card click whose settled frame simply had no counter in it, so the run
    # spends a bounded round re-reading instead of ending the run on that one frame.
    if not DEPLOY_NO_COUNTER.exists():
        pytest.skip('retained live pre-battle evidence is not present')
    from types import SimpleNamespace
    from maalimbus.storage import RunStore
    store = RunStore(tmp_path / 'user-run-ledger.json', [SimpleNamespace(slot=2)])
    scope = store.start()
    frames = [DEPLOY_NO_COUNTER] * 4
    device = FakeDevice([archived(frame) for frame in frames])
    observer = FrameObserver(tmp_path, [str(frame) for frame in frames])
    notes = Notes()
    runner = MirrorRunner(device,
                          settings={'rounds': 1, 'interval': 0.0, 'page_tries': 2,
                                    'recovery_tries': 0},
                          registry=json.loads(REGISTRY.read_text(encoding='utf-8')),
                          directory=tmp_path, observer=observer, journal=notes,
                          store=store, run_id=scope)
    result = runner.run(steps=4, interval=0.0, round_limit=4)

    rereads = [details for event, details in notes.events
               if event == 'deployment_counter_reread']
    assert len(rereads) == 1, 'the missing counter is a frame, not the end of the run'
    assert rereads[0]['reason'] == 'deployment_counter_not_read'
    assert result['passed'] is False
    assert result['reason'] == 'deployment_transaction_or_counter_missing'
    assert device.clicks == []


# The map page's own chrome is not a node. This window's frame-0021 was taken with the
# view pulled away from the nodes, and the only lit glyph left sat inside the
# "Exploring Floor 1" caption: the journal's window_intent asks for [278, 132, 40, 40],
# which the game ignores, so the run burned its map tries on the caption and on plain
# lattice guesses. A real node never overlaps those captions.
MAP_PANNED = ROOT / 'evidence/runtime/window-20261012-022147'
MAP_CHROME = [[58, 129, 334, 47], [62, 186, 136, 28]]
MAP_CHROME_CANDIDATE = [278, 132, 40, 40]
MAP_LATTICE_CANDIDATE = [1521, 307, 190, 190]


def test_the_pages_own_header_is_not_a_node_to_step_to():
    record = json.loads((MAP_PANNED / 'frame-0021.json').read_text(encoding='utf-8'))
    chrome = header_chrome(record)
    assert [list(box) for box in chrome[:2]] == MAP_CHROME
    assert inside_chrome(MAP_CHROME_CANDIDATE, chrome) is True
    assert inside_chrome(MAP_LATTICE_CANDIDATE, chrome) is False


def test_a_map_candidate_under_the_header_is_dropped(tmp_path):
    directory = tmp_path / 'runtime'
    directory.mkdir()
    shutil.copy(MAP_PANNED / 'frame-0021.png', directory / 'frame-0021.png')
    record = json.loads((MAP_PANNED / 'frame-0021.json').read_text(encoding='utf-8'))

    name, boxes = candidates_of(directory, record)

    assert name == 'frame-0021.png'
    assert MAP_CHROME_CANDIDATE not in boxes, 'the caption is chrome, not a step'
    assert MAP_LATTICE_CANDIDATE in boxes, 'the rest of the ordering is untouched'




# The game keeps the previous encounter's deployment, so the page the driver meets on the
# second battle already prints the saved order (live window-20261012-023229/frame-0068
# shows eight of them). The driver asks each card's own band and submits instead of
# clearing the team and re-picking it.
INHERITED_FRAME = ROOT / 'evidence/runtime/window-20261012-023229/frame-0068.json'
INHERITED_REASON = 'battle_button_submits_the_team'
CLEAR_REASON = 'clear_inherited_participant_order_before_saved_deployment'


def saved_deployment_order():
    from maalimbus.runtime_paths import data_directory
    from maalimbus.storage import SINNERS, ProfileStore
    profiles = ProfileStore(data_directory(ROOT) / 'user-team-profiles.json')
    saved = next((team for team in profiles.load() if team.slot == 2), None)
    assert saved is not None and saved.deployment, 'the saved team carries a deployment'
    return [SINNERS.index(sinner) + 1 for sinner in saved.deployment]


def inherited_page(numbers, counter=(12, 12)):
    """The live pre-battle frame, redrawn with its own counter and printed order."""
    from maalimbus.runner import controls_by_id
    from maalimbus.team_vision import assignment_box
    record = json.loads(INHERITED_FRAME.read_text(encoding='utf-8'))
    controls = controls_by_id(json.loads(REGISTRY.read_text(encoding='utf-8')))
    bands = [assignment_box(controls.get('pre_battle.card_%02d' % index))
             for index in range(1, 13)]
    counter_roi = (1680, 738, 180, 92)

    def inside(token, box):
        x, y, w, h = box
        cx, cy = token['box'][0] + token['box'][2] / 2, token['box'][1] + token['box'][3] / 2
        return x <= cx <= x + w and y <= cy <= y + h

    ocr = [token for token in record['ocr']
           if not any(band and inside(token, band) for band in bands)
           and not inside(token, counter_roi)]
    for card, number in enumerate(numbers, start=1):
        if number is None or not bands[card - 1]:
            continue
        x, y, w, h = bands[card - 1]
        ocr.append({'text': str(number), 'box': [x, y, w, h], 'score': 1.0})
    if counter:
        ocr.append({'text': '%d / %d' % counter, 'box': list(counter_roi), 'score': 1.0})
    record['ocr'] = ocr
    record.pop('image', None)
    return record


def deployment_window(tmp_path, record):
    from types import SimpleNamespace
    from maalimbus.storage import RunStore
    store = RunStore(tmp_path / 'user-run-ledger.json', [SimpleNamespace(slot=2)])
    scope = store.start()
    image = archived(INHERITED_FRAME)
    device = FakeDevice([image, image, image])
    observer = FrameObserver(tmp_path, [record, record, record])
    notes = Notes()
    runner = MirrorRunner(device, settings={'rounds': 1, 'interval': 0.0, 'page_tries': 2,
                                            'recovery_tries': 0},
                          registry=json.loads(REGISTRY.read_text(encoding='utf-8')),
                          directory=tmp_path, observer=observer, journal=notes,
                          store=store, run_id=scope)
    return runner, device, notes


def test_a_page_that_already_prints_the_saved_order_goes_straight_to_battle(tmp_path):
    if not INHERITED_FRAME.exists():
        pytest.skip('retained live pre-battle evidence is not present')
    order = saved_deployment_order()
    numbers = [None] * 12
    for position, card in enumerate(order, start=1):
        numbers[card - 1] = position
    runner, device, notes = deployment_window(tmp_path, inherited_page(numbers))
    result = runner.run(steps=1, interval=0.0, round_limit=1)

    assert result['steps'][0]['plan']['reason'] == INHERITED_REASON
    assert all(step['plan']['reason'] != CLEAR_REASON for step in result['steps'])
    assert runner.deployment_transaction.data['sequence'] == []
    assert len(device.clicks) == 1, 'the only input is Battle!'


def test_a_page_that_prints_another_order_is_cleared_before_the_saved_one(tmp_path):
    if not INHERITED_FRAME.exists():
        pytest.skip('retained live pre-battle evidence is not present')
    order = saved_deployment_order()
    shifted = [None] * 12
    for position, card in enumerate(order, start=1):
        shifted[card - 1] = position % 12 + 1
    runner, device, notes = deployment_window(tmp_path, inherited_page(shifted))
    result = runner.run(steps=1, interval=0.0, round_limit=1)
    assert result['steps'][0]['plan']['reason'] == CLEAR_REASON
    assert len(device.clicks) == 1


OBSERVATION_RECORD = {'event': 'map_observed', 'scene': 'MAP', 'frame': 'frame-0002'}


def silent_node(directory, record=None, on_call=None):
    """A pipeline node that records nothing, or records on the call it is told to."""
    calls = []

    def run(tasker, name, deadline=None):
        calls.append(name)
        if record is not None and (on_call is None or len(calls) == on_call):
            with (Path(directory) / 'events.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(record) + '\n')
    return run, calls


def test_an_observation_node_that_records_no_page_is_run_again(tmp_path, monkeypatch):
    """One silent node run is not a page: the node is re-run for this frame.

    The packaged agent stopped a live run on 'Deployment successor participant count
    not proven' while its click was already on the board, because the successor read
    returned the pre-click event (evidence/runtime/packaged-mirror-20261012-032032 has
    one map_observed and one frame for the whole run). A reader that reuses the newest
    event of its kind cannot see that, so the node runs again instead.
    """
    run, calls = silent_node(tmp_path, OBSERVATION_RECORD, on_call=2)
    monkeypatch.setattr(runner_module, 'run_node', run)
    record = MaaObserver(object(), tmp_path).observe()
    assert record['frame'] == 'frame-0002'
    assert calls == ['WindowMapObserve', 'WindowMapObserve']


def test_a_stale_page_is_never_returned_as_this_frame(tmp_path, monkeypatch):
    """A page recorded before this call is not this frame's page."""
    (tmp_path / 'events.jsonl').write_text(
        json.dumps({'event': 'map_observed', 'scene': 'PRE_BATTLE_TEAM',
                    'participant_texts': ['2/12']}) + '\n', encoding='utf-8')
    run, calls = silent_node(tmp_path)
    monkeypatch.setattr(runner_module, 'run_node', run)
    with pytest.raises(RuntimeError, match='observation node recorded no page'):
        MaaObserver(object(), tmp_path).observe()
    assert len(calls) == 2, 'a silent node is retried, then the run stops with the reason'


def test_a_battle_frame_whose_observation_records_nothing_stops(tmp_path, monkeypatch):
    """The battle node is guarded the same way as the map node."""
    run, calls = silent_node(tmp_path, {'event': 'map_observed', 'scene': 'BATTLE_HUD',
                                        'frame': 'frame-0002'}, on_call=1)
    monkeypatch.setattr(runner_module, 'run_node', run)
    with pytest.raises(RuntimeError, match='battle observation node recorded no page'):
        MaaObserver(object(), tmp_path).observe()
    assert calls == ['WindowMapObserve', 'WindowBattleObserve', 'WindowBattleObserve']


def test_a_live_page_keeps_the_native_local_reads_of_its_frame(tmp_path):
    """The unavailable-card proof has to survive the live observer seam.

    ``MaaObserver`` answers with the semantic ``map_observed`` event, whose payload
    carries no ``local_ocr``, while the frame the same step wrote carries the native
    ``deployment_availability`` record. Without that record every live
    PRE_BATTLE_TEAM step read an 11-card capacity with no unavailable card, spent
    both re-reads and stopped on 'Current deployment capacity requires independent
    unavailable-card proof' while the frame itself held ``accepted: true`` and
    ``unavailable: [6]`` (evidence/runtime/window-20261012-202916/frame-0003.json,
    written by the run that stopped). ``size`` and ``ocr`` were already attached
    here; the native reads are attached for the same reason, and a frame record
    that already carries its own is never overwritten.
    """
    proof = {'purpose': 'deployment_availability', 'accepted': True, 'participants': [0, 11],
             'unavailable': [6], 'teacher': 'native_hp_and_card_pixels'}
    (tmp_path / 'frame-0002.json').write_text(json.dumps({
        'image_sha256': 'a' * 64, 'size': [1920, 1080],
        'ocr': [{'text': '0/ 11', 'box': [1680, 738, 180, 92], 'score': .894}],
        'local_ocr': [proof]}), encoding='utf-8')

    class SilentEvent:
        directory = tmp_path

        def observe(self, *, deadline=None):
            return {'event': 'map_observed', 'scene': 'PRE_BATTLE_TEAM', 'frame': 'frame-0002'}

    record = observe(SilentEvent())
    assert record['local_ocr'] == [proof]
    controls = {'pre_battle.card_%02d' % index: [0, 0, 1, 1] for index in range(1, 13)}
    team = team_state(record, controls)
    assert team['availability']['accepted'] is True, 'the proof reaches the pre-battle reader'
    assert team['unavailable'] == [6], 'and with it the card the page cannot field'


def test_a_record_that_already_carries_its_local_reads_keeps_them(tmp_path):
    """A replayed frame is its own evidence: the seam never rewrites it."""
    own = {'purpose': 'deployment_availability', 'accepted': False, 'participants': [0, 12]}
    (tmp_path / 'frame-0002.json').write_text(json.dumps({
        'image_sha256': 'b' * 64, 'size': [1920, 1080], 'ocr': [], 'local_ocr': [own]}),
        encoding='utf-8')

    class Event:
        directory = tmp_path

        def observe(self, *, deadline=None):
            return {'event': 'map_observed', 'scene': 'PRE_BATTLE_TEAM', 'frame': 'frame-0002',
                    'local_ocr': [own]}

    assert observe(Event())['local_ocr'] == [own]


SHOP_DIR = ROOT / 'evidence/runtime/window-20261012-024300'
SHOP_FRAME = SHOP_DIR / 'frame-0173.json'
SHOP_REASON_BUY = 'the_gift_plan_asked_for_this_offer_and_the_shop_covers_it'
SHOP_REASON_NONE = 'no_offer_matches_the_gift_plan'
SHOP_REASON_BOUGHT = 'every_offer_the_gift_plan_asked_for_was_already_bought'
# The cap's own line was crossed and it still bought nothing: the reason has to name
# that state, not the gift plan's, or a live trace cannot tell a shelf that had
# nothing to sell from a plan that simply wanted nothing.
SHOP_REASON_CAP_UNMET = ('the_visit_would_carry_out_more_coins_than_its_cap_holds_but_no_'
                         'affordable_unbought_offer_the_shelf_prints_is_the_catalogs')


def shop_page():
    """The live shop page as the loop reads it."""
    if not SHOP_FRAME.exists():
        pytest.skip('retained live shop evidence is not present')
    record=json.loads(SHOP_FRAME.read_text(encoding='utf-8'))
    # Runtime narrow native reads repair the icon-prefixed low-confidence badge.
    record['ocr']=[t for t in record['ocr'] if t['text']!='015']
    record['ocr'].append(dict(text='15',score=.999732,box=[1489,214,39,46]))
    return record


def shop_window(tmp_path, record, extras=None):
    """A one-step window sitting on the shop page, with the run's own store.

    ``extras`` replaces the three identical observations with its own records, so a
    test can hand the loop a page that changes between steps.
    """
    from types import SimpleNamespace
    from maalimbus.storage import RunStore,ProfileStore
    from maalimbus.policies import Team
    ProfileStore(tmp_path/'user-team-profiles.json').save([Team(2,frozenset({'Bleed'}))])
    store = RunStore(tmp_path / 'user-run-ledger.json', [SimpleNamespace(slot=2)])
    scope = store.start()
    image = archived(SHOP_FRAME)
    device = FakeDevice([image, image, image])
    records = ([dict(record,image=image)]*3 if extras is None
               else [dict(extra,image=image) for extra in extras])
    observer = FrameObserver(tmp_path, records)
    notes = Notes()
    runner = MirrorRunner(device, settings={'rounds': 1, 'interval': 0.0, 'page_tries': 2,
                                            'recovery_tries': 0},
                          registry=json.loads(REGISTRY.read_text(encoding='utf-8')),
                          directory=tmp_path, observer=observer, journal=notes,
                          store=store, run_id=scope)
    return runner, device, notes


def test_the_shop_page_is_read_for_the_one_offer_the_plan_asked_for():
    from maalimbus.runner import shop_state
    page = shop_page()
    state = shop_state(page, wanted=['Prejudice'])
    assert state['currency'] == 1008
    assert state['buy']['name'] == 'Prejudice' and state['buy']['price'] == 152
    assert state['buy']['box'] == [1101, 585, 120, 90]
    assert state['reason'] == SHOP_REASON_BUY
    assert state['confirm'] is None, 'the shop itself is not a purchase question'
    # The shelf's leftmost card is the replacement announcement.  Its 77 badge scored
    # .8348, so the old .9 shelf filter threw the price away and left the name unpaired
    # -- a card that is plainly on screen vanished from the plan.  It is reported now.
    assert [offer['name'] for offer in state['offers']] == [
        'Replace Heathciffs Skill', 'Uncapped Defibrilator', 'Polarization',
        'Scalpel', 'Curriculum Vitae', 'Prejudice']


def test_a_plan_the_shelf_does_not_hold_buys_nothing_and_may_refresh():
    from maalimbus.runner import shop_state
    page = shop_page()
    state = shop_state(page, wanted=['Wound Clerid'])
    assert state['buy'] is None and state['reason'] == SHOP_REASON_NONE
    # The shelf prints a plain Refresh for 15 and the page holds 1008, so one refresh
    # is worth taking; it is the only input a shop visit may spend beyond a purchase.
    assert state['refresh']['cost'] == 15
    assert state['refresh']['reason'] == 'no_offer_matches_the_gift_plan_yet'
    again = shop_state(page, wanted=['Wound Clerid'], refreshes_used=2, refresh_limit=2)
    assert again['refresh'] is None, 'a visit pays for no more refreshes than it is allowed'
    # A page whose currency token was not read cannot price a refresh against the
    # reserve, so it offers none: the shelf is refreshed only when it is paid for.
    unread = dict(page, ocr=[token for token in page['ocr']
                             if token['text'].strip() != '1008'])
    poor = shop_state(unread, wanted=['Wound Clerid'])
    assert poor['currency'] is None and poor['refresh'] is None
    assert poor['reason'] == 'shop_currency_not_read'


def test_a_plan_with_no_names_never_refreshes_the_shelf():
    from maalimbus.runner import shop_state
    page = shop_page()
    state = shop_state(page, wanted=[])
    assert state['buy'] is None and state['refresh'] is None
    assert state['reason'] == SHOP_REASON_NONE


def test_an_offer_this_run_already_paid_for_is_not_paid_for_again():
    from maalimbus.runner import shop_state
    page = shop_page()
    state = shop_state(page, wanted=['Prejudice'], bought=['Prejudice'])
    assert state['buy'] is None and state['reason'] == SHOP_REASON_BOUGHT


SHOP_REASON_CAP = ('the_visit_would_carry_out_more_coins_than_its_cap_holds_so_'
                   'the_shelf_is_spent_on')


def test_a_visit_that_would_carry_out_more_than_its_cap_spends_the_surplus():
    """The operator's directive: keep 500, carry at most 1500 out of a visit.

    The plan wants a gift this shelf does not hold and the visit has no refresh left, so
    without the cap it would walk out with all 1008 coins (the live run pi-20261012-174217
    did exactly that with 2518).  The surplus buys the cheapest card the shelf itself
    printed, and it is reported as the cap's purchase rather than as the plan's.
    """
    from maalimbus.runner import shop_state
    page = shop_page()
    state = shop_state(page, wanted=['Wound Clerid'], refreshes_used=2, refresh_limit=2,
                       reserve_coins=500, carry_cap_coins=800)
    assert state['refresh'] is None
    assert state['buy'] == {'box': [870, 357, 120, 90], 'name': 'Replace Heathciffs Skill',
                            'price': 77, 'index': 1, 'why': 'carry_cap'}
    assert state['reason'] == SHOP_REASON_CAP


def test_the_cap_never_pays_more_than_the_visit_may_carry_or_buy_a_blocked_offer():
    from maalimbus.runner import shop_state
    page = shop_page()
    # A reserve above the coins on the page leaves nothing to spend: the cap is a rule
    # about surplus, never a reason to break the floor the player set.
    poor = shop_state(page, wanted=['Wound Clerid'], refreshes_used=2, refresh_limit=2,
                      reserve_coins=1000, carry_cap_coins=800)
    assert poor['buy'] is None and poor['reason'] == SHOP_REASON_CAP_UNMET
    # A blocked name is skipped for the next cheapest printed offer, and when the player
    # blocked the whole shelf the visit leaves with its coins rather than buying anything.
    blocked = shop_state(page, wanted=['Wound Clerid'], refreshes_used=2, refresh_limit=2,
                         reserve_coins=500, carry_cap_coins=800,
                         blocked=['Replace Heathciffs Skill'])
    assert blocked['buy']['name'] == 'Uncapped Defibrilator'
    assert blocked['buy']['price'] == 147 and blocked['buy']['why'] == 'carry_cap'
    every = shop_state(page, wanted=['Wound Clerid'], refreshes_used=2, refresh_limit=2,
                       reserve_coins=500, carry_cap_coins=800,
                       blocked=[offer['name'] for offer in page_offers(page)])
    assert every['buy'] is None and every['reason'] == SHOP_REASON_CAP_UNMET


def test_the_cap_only_spends_on_an_offer_the_gift_catalog_names():
    """The shelf also sells services, and one of them derailed a live run.

    ``window-20261012-210547/frame-0005.json`` printed ``Replace Don Qubote's Sil`` at 77
    among the shelf's cards; the catalog names no such offer, and clicking it opened the
    skill-replacement chooser instead of the shop's own purchase question
    (``frame-0006.json``, an UNKNOWN_DIALOG whose only safe control is Cancel).  When the
    catalog's vocabulary is supplied, the cap skips every offer it does not name.
    """
    from maalimbus.runner import shop_state
    page = shop_page()
    named = shop_state(page, wanted=['Wound Clerid'], refreshes_used=2, refresh_limit=2,
                       reserve_coins=500, carry_cap_coins=800, gift_names=('Scalpel',))
    assert named['buy']['name'] == 'Scalpel' and named['buy']['price'] == 155
    assert named['buy']['why'] == 'carry_cap'
    unknown = shop_state(page, wanted=['Wound Clerid'], refreshes_used=2, refresh_limit=2,
                         reserve_coins=500, carry_cap_coins=800,
                         gift_names=('No Such Gift',))
    assert unknown['buy'] is None and unknown['reason'] == SHOP_REASON_CAP_UNMET
    # An empty vocabulary is how every caller that has no catalog keeps the old rule.
    everything = shop_state(page, wanted=['Wound Clerid'], refreshes_used=2, refresh_limit=2,
                            reserve_coins=500, carry_cap_coins=800, gift_names=())
    assert everything['buy']['name'] == 'Replace Heathciffs Skill'


def page_offers(page):
    from maalimbus.runner import shop_state
    return shop_state(page, wanted=['Wound Clerid'])['offers']


def test_the_cap_waits_for_the_plan_and_its_refresh_and_only_fires_above_itself():
    """Order: the gift plan first, then a refresh worth taking, then the cap, and never
    below the cap itself; ``None`` leaves the rule off entirely."""
    from maalimbus.runner import shop_state
    page = shop_page()
    plan = shop_state(page, wanted=['Prejudice'], refreshes_used=2, refresh_limit=2,
                      reserve_coins=500, carry_cap_coins=800)
    assert plan['buy']['name'] == 'Prejudice' and plan['buy']['why'] == 'gift_plan'
    fresh = shop_state(page, wanted=['Wound Clerid'], refreshes_used=0, refresh_limit=2,
                       reserve_coins=500, carry_cap_coins=800)
    assert fresh['buy'] is None and fresh['refresh']['cost'] == 15
    above = shop_state(page, wanted=['Wound Clerid'], refreshes_used=2, refresh_limit=2,
                       reserve_coins=500, carry_cap_coins=1500)
    assert above['buy'] is None and above['reason'] == SHOP_REASON_NONE
    off = shop_state(page, wanted=['Wound Clerid'], refreshes_used=2, refresh_limit=2,
                     reserve_coins=500)
    assert off['buy'] is None and off['reason'] == SHOP_REASON_NONE


def test_the_shop_page_is_not_read_when_the_page_is_not_a_shop():
    from maalimbus.runner import shop_state
    page = shop_page()
    page = dict(page, scene='MAP')
    assert shop_state(page, wanted=['Prejudice']) is None


def test_the_purchase_question_offers_only_the_confirm_it_printed():
    from maalimbus.runner import shop_state
    page = dict(shop_page(), scene='SHOP_PURCHASE',
                ocr=shop_page()['ocr'] + [{'text': 'Confirm', 'box': [1116, 722, 110, 34],
                                           'score': 1.0},
                                          {'text': 'X Cancel', 'box': [706, 720, 138, 36],
                                           'score': .94}])
    state = shop_state(page, wanted=['Prejudice'])
    # The frame still carries the question's own Confirm and the scene read still finds
    # it -- but the shop state never hands it over: only the runner's SHOP_PURCHASE
    # branch may, and only from an account it can prove.  The live 21:24:38 run ended
    # because a scene read was planned as an authorization.
    assert state['confirm'] is None
    assert state['buy'] is None and state['refresh'] is None
    assert state['reason'] == 'the_shop_asked_about_a_purchase_and_its_confirm_is_the_only_input'
    # A question whose Confirm the frame did not carry is not answered at all: the
    # plan records it instead of buying, refreshing or leaving behind the question.
    unread = dict(page, ocr=[token for token in page['ocr'] if token['text'] != 'Confirm'])
    unread = dict(unread, ocr=[token for token in unread['ocr'] if token['text'] != 'X Cancel'])
    bare = shop_state(unread, wanted=['Prejudice'])
    assert bare['confirm'] is None and bare['buy'] is None and bare['refresh'] is None
    assert bare['reason'] == 'the_shop_asked_about_a_purchase_and_its_confirm_was_not_read'


def test_a_purchase_attempt_is_reserved_without_claiming_it_was_bought(tmp_path):
    """A click reserves its intent; only a separately proven receipt books a purchase."""
    runner, device, notes = shop_window(tmp_path, shop_page())
    from maalimbus.storage import ProfileStore
    from maalimbus.policies import Team
    ProfileStore(tmp_path/'user-team-profiles.json').save([
        Team(2,frozenset({'Bleed'}),allow=frozenset({'Prejudice'}))])
    runner.state['gift_plan'] = {'teams': {'bleed': ['Prejudice']}, 'default': []}
    runner.run(steps=1, interval=0.0, round_limit=1)
    sent = [details for event, details in notes.events if event == 'shop_purchase_sent']
    assert len(sent) == 1
    assert sent[0]['gift'] == 'Prejudice' and sent[0]['price'] == 152
    assert runner.state['shop_bought']==[]
    pending=runner.shop_transaction.data['pending']
    assert (pending['name'],pending['price'],pending['coins'])==('Prejudice',152,1008)
    assert pending['before']['path'].endswith('.json')
    assert not sent[0]['receipt_verified']
    page_notes = [details for event, details in notes.events if event == 'shop_offers']
    assert page_notes and page_notes[0]['buy']['name'] == 'Prejudice'


def test_a_refresh_is_booked_against_the_visit_that_paid_for_it(tmp_path):
    runner, device, notes = shop_window(tmp_path, shop_page())
    runner.state['gift_plan'] = {'teams': {'bleed': ['Wound Clerid']}, 'default': []}
    runner.run(steps=1, interval=0.0, round_limit=1)
    assert runner.state['shop_refreshes'] == 1
    assert [details for event, details in notes.events if event == 'shop_shelf_refreshed']
    intents = [details for event, details in notes.events if event == 'window_intent']
    assert intents[0]['reason'] == 'refreshing_the_shelf_for_the_gift_the_plan_wants'


def test_a_refresh_successor_read_mid_change_waits_before_it_stops(tmp_path):
    """A shelf caught mid-redraw is a wait, not a stop; the wait is bounded and books nothing."""
    page = shop_page()
    dropped = {'Uncapped Defibrilator','Polarization','Scalpel','Curriculum Vitae'}
    sparse = dict(page, ocr=[token for token in page['ocr'] if token['text'] not in dropped])
    runner, device, notes = shop_window(tmp_path, page,
                                        extras=[page] + [sparse] * 11)
    runner.state['gift_plan'] = {'teams': {'bleed': ['Wound Clerid']}, 'default': []}
    runner.run(steps=5, interval=0.0, round_limit=5)
    waits = [details for event, details in notes.events if event == 'shop_refresh_settling']
    assert [wait['attempt'] for wait in waits] == [1, 2, 3]
    assert all(wait['input_sent'] is False for wait in waits)
    assert not [details for event, details in notes.events if event == 'shop_receipt_verified']
    # The fourth unproven read is the last one: an unchanged page still stops the window,
    # and the refresh intent stays unclaimed because nothing proved it was paid for.  This
    # harness replays one image, so that read stops on the frame-identity guard rather than
    # on the delta; the live run stopped on the delta from a genuinely redrawn frame.
    assert runner.artifacts['steps'][-1].get('stopped')
    assert runner.shop_transaction.data['pending']['kind'] == 'refresh'


def test_a_shop_visit_that_spent_its_refreshes_leaves_instead(tmp_path):
    runner, device, notes = shop_window(tmp_path, shop_page())
    runner.settings.shop_refreshes = 0
    runner.state['gift_plan'] = {'teams': {'bleed': ['Wound Clerid']}, 'default': []}
    runner.run(steps=1, interval=0.0, round_limit=1)
    assert runner.state['shop_refreshes'] == 0
    intents = [details for event, details in notes.events if event == 'window_intent']
    assert intents[0]['reason'] == 'leaving_the_shop_is_the_only_budget_safe_input'


def _dead_key_deployment(path, dead=6):
    """A deployment store whose own proof could not field `dead` in a key saved slot."""
    from maalimbus.storage import write_json
    order = [dead, 2, 4, 9, 12, 7, 11, 10, 3, 1, 8, 5]
    write_json(path, dict(scope='run', sequence=[], pending=None, saved_order=order,
                          order=order, unavailable=[dead]))
    return path


def _counter_lower(record, delta):
    """The same shop frame with the shop's own counter read `delta` lower."""
    from maalimbus.shop_vision import CURRENCY_X, CURRENCY_Y

    def inside(box):
        cx, cy = box[0] + box[2] / 2.0, box[1] + box[3] / 2.0
        return CURRENCY_X[0] <= cx <= CURRENCY_X[1] and CURRENCY_Y[0] <= cy <= CURRENCY_Y[1]

    counter = [token for token in record['ocr'] if inside(token['box'])]
    assert len(counter) == 1, counter
    patched = json.loads(json.dumps(record))
    for token in patched['ocr']:
        if token['box'] == counter[0]['box']:
            token['text'] = str(int(counter[0]['text']) - delta)
    return patched


def test_the_shop_sells_a_dead_key_slot_back_and_books_it_from_its_own_counter(tmp_path):
    """The Heal Sinner service is planned from the deck's proof and booked by its price.

    A Sinner the deployment page's own proof could not field whose saved slot is among the
    first seven comes back first, before the visit spends anything else, and the revive is
    paid for out of the run's own currency.  The only receipt that books it is the shop's
    counter moving by exactly the price the modal printed (live 2026-10-12: 1008 -> 908 for
    Hong Lu's 100).
    """
    from maalimbus.deployment_transaction import DeploymentTransaction
    from maalimbus.shop_revive import heal_sinner
    from maalimbus.vision import Text
    page = shop_page()
    runner, device, notes = shop_window(tmp_path, page)
    image = runner.observer.frames[0]['image']
    store = _dead_key_deployment(tmp_path / 'deployment.json')
    runner.deployment_transaction = DeploymentTransaction(store)
    runner.state['gift_plan'] = {'teams': {'bleed': ['Prejudice']}, 'default': []}
    result = runner.step()
    assert result['page'] == 'SHOP'
    # The service click is the input; whether the frame after it is accepted is a separate
    # question, so the intent is read where the run writes it before sending the click.
    intents = [details for event, details in notes.events if event == 'window_intent']
    assert intents and intents[0]['reason'] == 'a_key_saved_slot_is_dead_and_the_shop_sells_the_way_back'
    service = heal_sinner([Text(t['text'], tuple(t['box']), t['score']) for t in page['ocr']],
                          page.get('size'))
    assert intents[0]['target'] == list(service.box)
    planned = [details for event, details in notes.events if event == 'shop_revive_planned']
    assert len(planned) == 1 and planned[0]['cards'] == [6]
    assert (planned[0]['cost'], planned[0]['coins_before']) == (100, 1008)
    assert runner.state['revive_receipt'] == dict(card=6, cost=100, coins_before=1008)
    assert [details for event, details in notes.events if event == 'shop_purchase_sent'] == []
    # The next shop frame is the one the revive left behind: its own counter is 100 lower,
    # the price the modal printed, so that frame is the receipt and the store books it.
    after = dict(_counter_lower(page, 100), image=image)
    runner.observer.frames, runner.observer.index = [after] * 4, 0
    result = runner.step()
    assert result['page'] == 'SHOP'
    booked = [details for event, details in notes.events if event == 'shop_revive_booked']
    assert len(booked) == 1 and booked[0]['coins_after'] == 908
    assert booked[0]['proof']['source'] == 'shop_currency_delta'
    assert DeploymentTransaction(store).data['revives'] == [
        dict(card=6, cost=100, coins_before=1008, coins_after=908, proof=booked[0]['proof'])]
    # The booked receipt is what keeps the same Sinner from being bought back twice: the
    # store's own dead list no longer names card 6.
    from maalimbus.shop_revive import key_losses, saved_order, unavailable_sinners
    assert unavailable_sinners(DeploymentTransaction(store).data) == []
    assert key_losses([], saved_order(DeploymentTransaction(store).data)) == []


def test_a_counter_that_does_not_show_the_revive_price_books_nothing(tmp_path):
    """A frame after the revive that kept the same counter is recorded, never believed."""
    from maalimbus.deployment_transaction import DeploymentTransaction
    page = shop_page()
    runner, device, notes = shop_window(tmp_path, page)
    image = runner.observer.frames[0]['image']
    store = _dead_key_deployment(tmp_path / 'deployment.json')
    runner.deployment_transaction = DeploymentTransaction(store)
    runner.state['revive_receipt'] = dict(card=6, cost=100, coins_before=1008)
    runner.observer.frames, runner.observer.index = [dict(page, image=image)] * 4, 0
    runner.step()
    unproven = [details for event, details in notes.events
                if event == 'shop_revive_receipt_not_proven']
    assert len(unproven) == 1 and unproven[0]['coins_after'] == 1008
    assert unproven[0]['reason'] == 'the_shop_s_counter_did_not_show_the_revive_price'
    assert DeploymentTransaction(store).data.get('revives') in (None, [])


REVIVE_PICK_FRAME = ROOT / 'evidence/runtime/window-20261012-213008/frame-0002.json'
REVIVE_PICKED_FRAME = ROOT / 'evidence/runtime/window-20261012-214635/frame-0006.json'
REVIVE_DONE_FRAME = ROOT / 'evidence/runtime/window-20261012-214803/frame-0001.json'


def revive_frame(path, words):
    """A retained revive frame as the live recognition layer names it today."""
    from maalimbus.vision import Text, classify
    if not path.exists():
        pytest.skip('retained live revive evidence is not present')
    record = json.loads(path.read_text(encoding='utf-8'))
    rows = [Text(t['text'], tuple(t['box']), t['score']) for t in record['ocr']]
    return dict(record, scene=classify(rows, words, record.get('size') or (1920, 1080)),
                image=archived(path))


def revive_window(tmp_path, frames):
    """A window walking revive frames in order, with the run's own stores."""
    from types import SimpleNamespace
    from maalimbus.policies import Team
    from maalimbus.storage import ProfileStore, RunStore
    ProfileStore(tmp_path/'user-team-profiles.json').save([Team(2,frozenset({'Bleed'}))])
    store = RunStore(tmp_path / 'user-run-ledger.json', [SimpleNamespace(slot=2)])
    scope = store.start()
    device = FakeDevice([frame['image'] for frame in frames])
    observer = FrameObserver(tmp_path, [dict(frame) for frame in frames])
    notes = Notes()
    runner = MirrorRunner(device, settings={'rounds': 1, 'interval': 0.0, 'page_tries': 2,
                                            'recovery_tries': 0},
                          registry=json.loads(REGISTRY.read_text(encoding='utf-8')),
                          directory=tmp_path, observer=observer, journal=notes,
                          store=store, run_id=scope)
    return runner, device, notes


def test_the_picker_names_the_dead_card_and_the_modal_answers_its_own_pick(tmp_path):
    """The revive's whole second step, walked on the frames the live run left behind.

    window-20261012-213008/frame-0002 is the picker before anything was picked: it asks for
    the Sinner and prints no bottom button, so the one input it can take is the dead card's
    own portrait in the party bar.  window-20261012-214635/frame-0006 is the same step after
    that pick, where the modal's own 'Select' [1614,937,166,61] answers it; and
    window-20261012-214803/frame-0001 is what the revive printed -- "Hong Lu, revived,
    returns to battle." over 'Leave' [1622,943,150,53].  Which card is dead is never guessed
    from a portrait: it is the deployment store's own proof.
    """
    from maalimbus.deployment_transaction import DeploymentTransaction
    from maalimbus.shop_revive import key_losses, picker_slot, saved_order, unavailable_sinners
    words = json.loads((ROOT / 'assets/resource/en/locale.json').read_text(encoding='utf-8'))
    pick = revive_frame(REVIVE_PICK_FRAME, words)
    picked = revive_frame(REVIVE_PICKED_FRAME, words)
    done = revive_frame(REVIVE_DONE_FRAME, words)
    shop = dict(shop_page(), image=archived(SHOP_FRAME))
    assert (pick['scene'], picked['scene'], done['scene']) == (
        'REVIVE_PICK', 'REVIVE_PICK', 'REVIVE_DONE'), 'the rules name these frames'
    runner, device, notes = revive_window(tmp_path, [pick, picked, picked, done, done, shop])
    store = _dead_key_deployment(tmp_path / 'deployment.json')
    runner.deployment_transaction = DeploymentTransaction(store)
    # Only an input the frame itself argues for: the dead card's slot, from the deck proof.
    result = runner.step()
    assert result['page'] == 'REVIVE_PICK'
    bound = [details for event, details in notes.events if event == 'revive_pick_slot_bound']
    data = DeploymentTransaction(store).data
    assert len(bound) == 1 and bound[0]['cards'] == key_losses(unavailable_sinners(data),
                                                              saved_order(data)) == [6]
    assert bound[0]['box'] == list(picker_slot(unavailable_sinners(data), saved_order(data)))
    intents = [details for event, details in notes.events if event == 'window_intent']
    assert intents[-1]['reason'] == \
        'picking_the_dead_key_slot_the_deployment_page_could_not_field'
    assert intents[-1]['target'] == bound[0]['box']
    # The first picker frame prints no button, so nothing but a portrait could be answered.
    assert not [details for event, details in notes.events
                if event == 'revive_pick_confirm_bound']
    # The picker answers the portrait with itself, and now the modal's own button is there.
    result = runner.step()
    assert result['page'] == 'REVIVE_PICK'
    confirm = [details for event, details in notes.events if event == 'revive_pick_confirm_bound']
    assert len(confirm) == 1 and confirm[0]['box'] == [1614, 937, 166, 61]
    intents = [details for event, details in notes.events if event == 'window_intent']
    assert intents[-1]['reason'] == 'the_modals_own_button_answers_the_pick_the_bar_made'
    assert intents[-1]['target'] == [1614, 937, 166, 61]
    # And the notice the revive printed is left by its own button, never by 'Heal again.'.
    result = runner.step()
    assert result['page'] == 'REVIVE_DONE'
    leave = [details for event, details in notes.events if event == 'revive_done_leave_bound']
    assert len(leave) == 1 and leave[0]['box'] == [1622, 943, 150, 53]
    intents = [details for event, details in notes.events if event == 'window_intent']
    assert intents[-1]['reason'] == 'the_revive_is_paid_for_and_the_modal_leaves_back_to_the_shop'
    assert intents[-1]['target'] == [1622, 943, 150, 53]


def test_a_floor_that_refused_every_click_is_not_reported_as_an_unread_map():
    """The two map stops are different failures and must not share a name.

    Live ``evidence/runtime/packaged-mirror-20261021-202503`` sent seven inputs to
    nodes the game never accepted and then reported ``no_candidate_node_observed``,
    which reads as "the reader missed a node" -- so the next change chased the
    reader instead of the page.
    """
    from maalimbus.runner import map_stop_reason

    assert map_stop_reason(tried=(), attempts=3) == 'map_candidates_not_observed_yet'
    assert map_stop_reason(tried=((1152, 169, 190, 190),), attempts=0) == (
        'map_candidates_not_observed_yet')
    assert map_stop_reason(tried=((1152, 169, 190, 190),), attempts=2) == (
        'map_clicks_had_no_effect')


def test_a_run_whose_session_ended_never_reports_a_pass():
    """The step records can all be clean and the run can still be a failure.

    A failed pipeline node stops the loop before its next input, so the last step it
    wrote passed -- and the summary must not read that as "the window's steps passed".
    """
    runner = MirrorRunner(FakeDevice([]), settings={'rounds': 1, 'interval': 0.0})
    runner.state['session_ended'] = 'the_task_raised_before_the_next_input'
    runner.artifacts['steps'] = [{'passed': True, 'page_before': 'MAP', 'page_after': 'MAP'}]
    result = runner.summary()
    assert result['passed'] is False
    assert result['reason'] == 'the_task_raised_before_the_next_input'


def test_the_device_refuses_input_once_the_session_ended():
    """A failed pipeline node frees the controller with it.

    Posting a click afterwards reads through a released pointer -- a native access
    violation the interpreter cannot catch -- so the death is recorded on the device
    and every later input is refused by name instead.
    """
    import pytest as _pytest
    device = MaaDevice(StubController())
    assert device.ended is None
    device.end_session('the_pipeline_node_failed')
    assert device.ended == 'the_pipeline_node_failed'
    for call in (lambda: device.click(1, 2), lambda: device.swipe(1, 2, 3, 4, 500)):
        with _pytest.raises(RuntimeError) as error:
            call()
        assert 'refusing to post a' in str(error.value)
    device.end_session('some other reason')
    assert device.ended == 'the_pipeline_node_failed'
