"""Synthetic fixtures test evidence gates only, never model accuracy claims."""
import json,hashlib
from pathlib import Path
import cv2,numpy as np,pytest
from maalimbus.neural_shadow import detection_metrics,verified_model,verified_card_rois
from maalimbus.semantic_labels import persist_frame_proposals
from maalimbus.sinner_detection import LABELS
from maalimbus.storage import write_json
from maalimbus.learning_dataset import digest


def evaluation_data():
    samples=[];rows=[]
    for part in ('validation','test'):
        for negative in (False,True):
            sha=part+str(negative)
            boxes=[] if negative else [dict(label=l,box=[i*20,0,10,10]) for i,l in enumerate(LABELS)]
            samples.append(dict(image_sha256=sha,proof_sha256=sha+'proof',episode=part,
                split=part,size=[300,100],boxes=boxes))
            rows.append(dict(image_sha256=sha,proof_sha256=sha+'proof',episode=part,split=part,
                predictions=[dict(class_index=i,box=b['box'],score=.99) for i,b in enumerate(boxes)]))
    return dict(samples=samples,training_ready=True),rows


def test_native_metrics_account_for_duplicates_unknowns_and_negatives():
    data,rows=evaluation_data();assert detection_metrics(data,rows)['quality_passed']
    rows[0]['predictions'].append(dict(rows[0]['predictions'][0]))
    result=detection_metrics(data,rows)
    assert not result['quality_passed']
    assert result['metrics']['validation'][LABELS[0]]['fp']==1


@pytest.mark.parametrize('fault',['missing','duplicate','episode','proof','class','box','nan'])
def test_heldout_replay_binding_refuses(fault):
    data,rows=evaluation_data()
    if fault=='missing':rows.pop()
    elif fault=='duplicate':rows[-1]=dict(rows[0])
    elif fault=='episode':rows[0]['episode']='train'
    elif fault=='proof':rows[0]['proof_sha256']='changed'
    elif fault=='class':rows[0]['predictions'][0]['class_index']=12
    elif fault=='box':rows[0]['predictions'][0]['box']=[-1,0,10,10]
    else:rows[0]['predictions'][0]['score']=float('nan')
    with pytest.raises(ValueError):detection_metrics(data,rows)


def test_missing_class_and_missing_negative_cannot_pass():
    data,rows=evaluation_data();rows[0]['predictions'].pop()
    assert not detection_metrics(data,rows)['quality_passed']


def test_research_fit_metrics_never_claim_heldout_quality():
    data,rows=evaluation_data()
    for s in data['samples']:s['split']='train';s['episode']='one-real-episode'
    for r in rows:r['split']='train';r['episode']='one-real-episode'
    result=detection_metrics(data,rows,research_fit=True)
    assert result['research_fit_only'] and not result['quality_passed']
    assert not result['validation_and_test_independent']


def test_native_square_export_rechecks_actual_transform_bytes(tmp_path):
    from test_sinner_learning import ready
    from maalimbus.sinner_dataset import export,verify_export
    data=ready(tmp_path);out=tmp_path/'resized'
    export(tmp_path,data,out,native_resize=True)
    assert verify_export(tmp_path,out)==data
    image=next((out/'images').rglob('*.png'))
    assert cv2.imread(str(image)).shape[:2]==(640,640)
    cv2.imwrite(str(image),np.zeros((640,640,3),np.uint8))
    with pytest.raises(ValueError,match='resized'):verify_export(tmp_path,out)


def test_card_search_needs_native_controls_and_actual_visible_edges():
    image=np.zeros((1080,1920,3),np.uint8)
    record=dict(scene='PRE_BATTLE_TEAM',size=[1920,1080],ocr=[
        dict(text='Details',box=[1360,172,78,28],score=.99),
        dict(text='Battle!',box=[1672,859,146,44],score=.99)])
    assert verified_card_rois(image,record)==[]
    assert verified_card_rois(image,dict(record,scene='GIFT_PICK'))==[]
    assert verified_card_rois(image,None)==[]
    data,rows=evaluation_data();data['samples']=data['samples'][::2];rows=rows[::2]
    assert not detection_metrics(data,rows)['quality_passed']


def artifact(root):
    target=root/'model/detect';target.mkdir(parents=True)
    (target/'sinners.onnx').write_bytes(b'unit-test-artifact-not-real-model')
    native=dict(model_sha256=digest(target/'sinners.onnx'),dataset_manifest_sha256='dataset',
        recognizer='MaaFramework.NeuralNetworkDetect',input_sent=False,game_controller=False)
    write_json(target/'sinners.native-evaluation.json',native)
    card=dict(labels=list(LABELS),onnx_sha256=native['model_sha256'],dataset_manifest_sha256='dataset',
        training_complete=True,synthetic_model=False,native_evaluation_sha256=digest(target/'sinners.native-evaluation.json'))
    write_json(target/'sinners.model-card.json',card)
    return dict(labels=list(LABELS),model_sha256=native['model_sha256'],
        model_card_sha256=digest(target/'sinners.model-card.json'),production_enabled=False,input_authorized=False)


@pytest.mark.parametrize('fault',[None,'model','card','native','production'])
def test_shadow_artifacts_bound_before_native_inference(tmp_path,fault):
    policy=artifact(tmp_path);target=tmp_path/'model/detect'
    if fault in ('model','card','native'):
        name=dict(model='sinners.onnx',card='sinners.model-card.json',native='sinners.native-evaluation.json')[fault]
        (target/name).write_bytes(b'changed')
    elif fault=='production':policy['input_authorized']=True
    if fault:
        with pytest.raises((ValueError,json.JSONDecodeError)):verified_model(tmp_path,policy)
    else:assert verified_model(tmp_path,policy)[0]==policy['model_sha256']


def test_continuous_queue_idempotent_and_not_self_certified(tmp_path):
    frame=tmp_path/'frame.json';image=tmp_path/'frame.png'
    cv2.imwrite(str(image),np.zeros((32,32,3),np.uint8))
    write_json(frame,dict(size=[32,32],image_sha256=digest(image),scene='PRE_BATTLE_TEAM',
        ocr=[],neural_sinners=dict(status='shadow',model_sha256='model',
            boxes=[dict(class_id=0,box=[1,1,10,10],score=.99,reviewed=True)])))
    first=persist_frame_proposals(tmp_path,frame,'real-run','en',tmp_path/'queue')
    assert first==persist_frame_proposals(tmp_path,frame,'real-run','en',tmp_path/'queue')
    proposal=json.loads(Path(first['proposal']).read_text())
    assert proposal['boxes'][0]['reviewed'] is False and not proposal['training_eligible']
    cv2.imwrite(str(image),np.ones((32,32,3),np.uint8))
    with pytest.raises(ValueError,match='hash'):persist_frame_proposals(tmp_path,frame,'real-run','en',tmp_path/'queue')
