from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
import cv2,pytest
from maalimbus.storage import read_json
from maalimbus.overlay_dismissal import recognize
ROOT=Path(__file__).resolve().parents[1]


def actual():
    frame=ROOT/'evidence/runtime/sinner-sample-20261012-022801/frame-0004.json'
    if not frame.exists():pytest.skip('Actual private guide frame absent')
    return read_json(frame),cv2.imread(str(frame.with_suffix('.png')))


def hit(*args):
    return SimpleNamespace(hit=True,filtered_results=[SimpleNamespace(box=(110,50,64,42),score=.99)])


def test_known_guide_uses_own_back_and_not_page_triangle():
    record,image=actual();plan=recognize(hit,image,record)
    assert plan['box']==[110,50,64,42] and plan['kind']=='tutorial_book'
    assert plan['title']=='Creating your Team'
    assert not plan['input_authorized']


@pytest.mark.parametrize('fault',['resource_dialog','missing_header','low_header','missing_back','ambiguous_back','no_triangle'])
def test_unknown_or_ambiguous_overlay_does_not_invent_close(fault):
    record,image=actual();record=deepcopy(record);native=hit
    if fault=='resource_dialog':record['scene']='RUN_REWARD_DIALOG'
    elif fault=='missing_header':record['ocr']=[t for t in record['ocr'] if t['text']!='Creating your Team']
    elif fault=='low_header':next(t for t in record['ocr'] if t['text']=='Creating your Team')['score']=.8
    elif fault=='missing_back':native=lambda *a:SimpleNamespace(hit=False,filtered_results=[])
    elif fault=='ambiguous_back':native=lambda *a:SimpleNamespace(hit=True,filtered_results=[1,2])
    else:image=image.copy();image[450:740,1650:]=0
    assert recognize(native,image,record) is None
