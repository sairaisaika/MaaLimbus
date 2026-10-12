import copy
import hashlib
import json
import cv2
import numpy as np
import pytest
from maalimbus.storage import write_json
from maalimbus.unknown_exploration import Exploration,candidates


def frame(root,name,scene='UNKNOWN',value=0,labels=('Back',)):
    path=root/(name+'.json');image=np.full((108,192,3),value,dtype=np.uint8)
    cv2.imwrite(str(path.with_suffix('.png')),image)
    record=dict(scene=scene,size=[192,108],image_sha256=hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest(),
                ocr=[dict(text=t,box=[5+i*30,2,25,10],score=.99) for i,t in enumerate(labels)])
    write_json(path,record)
    return path,record


def test_success_keeps_before_after_input_and_review_together(tmp_path):
    before,r=frame(tmp_path,'before');after,_=frame(tmp_path,'after','MAP',20,())
    e=Exploration(tmp_path/'state.json',tmp_path/'review','run')
    e.reserve(before,e.choose(r),(10,6),450)
    resumed=Exploration(e.path,e.review_root,'run')
    assert resumed.choose(r) is None
    outcome=resumed.finish(after,'MAP')
    p=json.loads(open(outcome['proposal'],encoding='utf-8').read())
    assert outcome['success'] and p['proposed_label']=='return_overlay_to_MAP'
    assert not p['reviewed'] and not p['training_eligible'] and not p['input_authorized']
    bundle=e.review_root/next(e.review_root.iterdir()).name
    assert {x.name for x in bundle.iterdir()}=={'before.json','before.png','after.json','after.png','proposal.json','review.json','trace.log'}
    assert resumed.data['pending'] is None


def test_unchanged_input_is_not_replayed_and_alternate_controls_are_bounded(tmp_path):
    before,r=frame(tmp_path,'same',labels=('Back','Close','Return','戻る'))
    e=Exploration(tmp_path/'state.json',tmp_path/'review','run')
    for i in range(3):
        choice=e.choose(r);assert choice
        x,y,w,h=choice['box'];e.reserve(before,choice,(x+2,y+2),350)
        assert not e.finish(before,'UNKNOWN')['success']
    assert e.choose(r) is None and len(e.data['attempts'])==3


def test_changed_proof_preserves_pending_bytes(tmp_path):
    before,r=frame(tmp_path,'before');after,_=frame(tmp_path,'after','MAP',20)
    e=Exploration(tmp_path/'state.json',tmp_path/'review','run')
    e.reserve(before,e.choose(r),(10,6),500);saved=e.path.read_bytes()
    before.write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='proof changed'):e.finish(after,'MAP')
    assert e.path.read_bytes()==saved and e.data['pending']==0


@pytest.mark.parametrize('word',['Lunacy','Convert Enkephalin','Purchase','Give Up','To Window','Claim'])
def test_unknown_cost_or_exit_dialog_is_not_navigation(tmp_path,word):
    _,r=frame(tmp_path,'before',labels=('Back',word))
    assert candidates(r)==[]


def test_native_score_header_and_unique_caption_required(tmp_path):
    _,r=frame(tmp_path,'before')
    for change in ('low','outside','duplicate'):
        q=copy.deepcopy(r)
        if change=='low':q['ocr'][0]['score']=.94
        if change=='outside':q['ocr'][0]['box'][1]=60
        if change=='duplicate':q['ocr'].append(copy.deepcopy(q['ocr'][0]))
        assert not candidates(q)
