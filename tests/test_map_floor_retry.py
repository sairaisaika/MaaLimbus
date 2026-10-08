import json, shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from maalimbus.runner import MirrorRunner, FakeDevice, FrameObserver

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'evidence/runtime/window-20261008-123839/frame-0001.json'

@pytest.mark.parametrize('visible', [True,False])
def test_blinking_floor_retries_readonly_with_bounded_rounds(tmp_path,visible):
    paths=[]
    for i in range(3):
        data=json.loads(SOURCE.read_text())
        if visible and i==1:
            # Synthetic readable phase; no claim that this is live evidence.
            for t in data['ocr']:
                if t['text']=='Floor':t['text']='Floor 5'
        p=tmp_path/f'source-{i}.json';p.write_text(json.dumps(data))
        shutil.copyfile(SOURCE.with_suffix('.png'),p.with_suffix('.png'));paths.append(str(p))
    device=FakeDevice()
    runner=MirrorRunner(device,settings={'rounds':3,'interval':0,'stop_page':'MAP'},
        directory=tmp_path/'output',observer=FrameObserver(tmp_path/'output',paths))
    runner.theme_transaction=SimpleNamespace(data={'pending':{'floor':5}})
    runner.step()
    assert len(list((tmp_path/'output').glob('frame-*.json')))==(2 if visible else 3)
    assert device.clicks==[] and device.swipes==[] and device.keys==[]
    assert runner.theme_transaction.data['pending']=={'floor':5}
