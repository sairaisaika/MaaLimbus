import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from maalimbus.team_navigation import browse
from maalimbus.team_vision import selected_saved_team
from maalimbus.vision import Text
from maalimbus.window import plan_step

def row(n,y=470):return Text('TEAMS #%d'%n,(150,y,120,28),.99)

def test_visible_row_is_clicked_in_its_current_position_not_static_anchor():
    state={};location=browse([row(7),row(8,580)],(1920,1080),8,state)
    plan=plan_step('DUNGEON_TEAM',controls={'team.slot_08':[100,900,90,30]},
        team=dict(wanted=8,selected=7,visible_rows=location['rows'],visible_target=location['target']))
    assert plan['target']==[150,580,120,28] and not state

def test_offscreen_target_scrolls_up_then_stops_at_unchanged_boundaries():
    state={};rows=[row(7),row(8,580)]
    p=browse(rows,(1920,1080),2,state)
    assert p['direction']=='up' and p['to'][1]>p['start'][1]
    for _ in range(5):p=browse(rows,(1920,1080),2,state)
    assert p['reason']=='team_list_search_stalled' and state['attempts']<=5

def test_scroll_can_find_slot_22_and_header_must_independently_match():
    p=browse([row(7)],(1920,1080),22,{})
    plan=plan_step('DUNGEON_TEAM',team=dict(wanted=22,selected=7,visible_rows=p['rows'],navigation=p))
    assert plan['action']=='swipe' and plan['duration_ms']==600
    p=browse([row(22,650)],(1920,1080),22,{})
    assert p['target']==[150,650,120,28]
    assert selected_saved_team([Text('TEAMS #22',(334,170,116,28),.99)],(1920,1080))==22
    assert selected_saved_team([row(22)],(1920,1080)) is None

def test_ambiguous_or_unread_list_does_not_confirm_or_click_static_coordinates():
    p=browse([], (1920,1080),2,{})
    plan=plan_step('DUNGEON_TEAM',controls={'team.slot_02':[1,1,1,1]},
        team=dict(wanted=2,selected=7,visible_rows=[],navigation=p))
    assert plan['action']=='record'

def test_entry_frame_calls_global_reconcile_without_prior_shop_branch(tmp_path,monkeypatch):
    from maalimbus.runner import MirrorRunner,FakeDevice,FrameObserver,REGISTRY
    import cv2
    from maalimbus.storage import RunStore
    import maalimbus.runner as module
    frame=Path(__file__).resolve().parents[1]/'dist/MaaLimbus/evidence/runtime/pi-20261013-000909/frame-0005.json'
    if not frame.exists():pytest.skip('local failing entry frame not retained')
    monkeypatch.setenv('MAALIMBUS_DATA_PATH',str(tmp_path))
    store=RunStore(tmp_path/'user-run-ledger.json',[SimpleNamespace(slot=7)]);scope=store.start()
    calls=[];original=module.reconcile
    def track(*a,**kw):calls.append(kw['page']);return original(*a,**kw)
    monkeypatch.setattr(module,'reconcile',track)
    monkeypatch.setattr(module,'plan_step',lambda page,**kw:dict(page=page,action='record',
        target=None,expect=[],reason='entry_regression_checked'))
    device=FakeDevice([cv2.imread(str(frame.with_suffix('.png')))])
    instance=MirrorRunner(device,settings=dict(rounds=1,interval=0),directory=tmp_path,
        observer=FrameObserver(tmp_path,[str(frame)]),registry=json.loads(REGISTRY.read_text()),store=store,run_id=scope)
    result=instance.step()
    assert calls==['DUNGEON_TEAM'] and result['reason']=='entry_regression_checked'
    assert not device.clicks and not device.swipes and store.data['active']['id']==scope
