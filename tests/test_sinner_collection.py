from pathlib import Path
from copy import deepcopy
import pytest
from maalimbus.storage import read_json
from maalimbus.sinner_collection import home_sinners_target
from maalimbus.sinner_collection import reconcile
from maalimbus.storage import write_json
from maalimbus.learning_dataset import digest
ROOT=Path(__file__).resolve().parents[1]


def retained():
    p=ROOT/'evidence/runtime/window-20261008-190502/frame-0001.json'
    if not p.exists():pytest.skip('Private actual HOME frame absent')
    return read_json(p)


def test_independent_home_sinners_control():
    target=home_sinners_target(retained())
    assert target[2]>0 and target[3]>0


@pytest.mark.parametrize('fault',['scene','missing_drive','low_sinners','duplicate_sinners'])
def test_unknown_or_conflicting_menu_refuses(fault):
    record=deepcopy(retained());s=next(x for x in record['ocr'] if x['text']=='Sinners')
    if fault=='scene':record['scene']='RUN_REWARD_DIALOG'
    elif fault=='missing_drive':record['ocr']=[x for x in record['ocr'] if x['text']!='Drive']
    elif fault=='low_sinners':s['score']=.8
    else:record['ocr'].append(deepcopy(s))
    with pytest.raises(ValueError):home_sinners_target(record)


@pytest.mark.parametrize('fault',[None,'original_hash','successor_png','missing_header','tutorial'])
def test_fresh_library_resolves_original_menu_intent_without_repeating_input(tmp_path,fault):
    import shutil
    before_src=ROOT/'evidence/runtime/sinner-sample-20261012-022801/frame-0001.json'
    after_src=ROOT/'evidence/runtime/sinner-sample-20261012-023739/frame-0001.json'
    if not after_src.exists():pytest.skip('Actual collection successor absent')
    for source,name in ((before_src,'before'),(after_src,'after')):
        shutil.copy2(source,tmp_path/(name+'.json'));shutil.copy2(source.with_suffix('.png'),tmp_path/(name+'.png'))
    before=tmp_path/'before.json';after=tmp_path/'after.json';intent=tmp_path/'intent.json'
    state=dict(pending=True,expected_successor='TEAM_LIBRARY',before='before.json',
        before_sha256=digest(before),png_sha256=digest(tmp_path/'before.png'))
    record=read_json(after)
    if fault=='original_hash':state['before_sha256']='changed'
    elif fault=='successor_png':(tmp_path/'after.png').write_bytes(b'changed')
    elif fault=='missing_header':record['ocr']=[x for x in record['ocr'] if x['text']!='TEAMS']
    elif fault=='tutorial':record['scene']='TUTORIAL'
    write_json(after,record);write_json(intent,state);original=intent.read_bytes()
    if fault in ('original_hash','successor_png','missing_header'):
        with pytest.raises(ValueError):reconcile(tmp_path,intent,after)
        assert intent.read_bytes()==original
    elif fault=='tutorial':
        assert not reconcile(tmp_path,intent,after) and intent.read_bytes()==original
    else:
        assert reconcile(tmp_path,intent,after) and not read_json(intent)['pending']
