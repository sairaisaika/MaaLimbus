import hashlib,json
from pathlib import Path
from types import SimpleNamespace
import cv2,numpy as np,pytest
from maalimbus.sinner_detection import LABELS,proposals,native_pipeline
from maalimbus.sinner_dataset import manifest,export,verify_export,split
from maalimbus.neural_shadow import observe


def sample(root,index,episode):
    image=np.full((32,32,3),index%255,dtype=np.uint8)
    frame=root/f'{index}.png';cv2.imwrite(str(frame),image)
    boxes=[dict(label=l,box=[1,1,10,10]) for l in LABELS]
    row=dict(frame=frame.name,proof=f'{index}.json',episode=episode,locale='en',
             boxes=boxes,reviewed=True,complete=True)
    proof=dict(row,image_sha256=hashlib.sha256(frame.read_bytes()).hexdigest(),review_method='human_card_boundary')
    (root/row['proof']).write_text(json.dumps(proof))
    return row


def ready(root):
    episodes={p:[] for p in ('train','validation','test')}
    for n in range(200):
        p=split(str(n))
        if len(episodes[p])<3:episodes[p].append(str(n))
    rows=[sample(root,n+1,e) for n,e in enumerate(e for es in episodes.values() for e in es)]
    return manifest(root,rows,minimum=1)


def test_proposals_cannot_certify_themselves_and_numbers_skip_dante():
    rows=proposals(dict(size=[1920,1080]),[dict(class_index=9,score=.99,box=[5,6,100,200])])
    assert rows[0]['game_number']==11 and rows[0]['sinner']=='Sinclair'
    assert not rows[0]['reviewed'] and not rows[0]['training_eligible']
    pipeline=native_pipeline()
    assert len(pipeline)==12 and all(not n['enabled'] and n['action']['type']=='DoNothing' for n in pipeline.values())


@pytest.mark.parametrize('fault',[dict(class_index=12),dict(score=float('nan')),dict(box=[0,0,-1,2]),dict(box=[1920,0,1,1])])
def test_bad_detector_output_refuses(fault):
    d=dict(class_index=0,score=.99,box=[1,1,10,20]);d.update(fault)
    with pytest.raises(ValueError):proposals(dict(size=[1920,1080]),[d])


def test_duplicate_identity_is_queued_and_low_confidence_is_not_truth():
    d=dict(class_index=0,score=.99,box=[1,1,10,20])
    assert all(x['review_reason']=='duplicate_identity' for x in proposals(dict(size=[100,100]),[d,d]))
    assert proposals(dict(size=[100,100]),[dict(d,score=.1)])==[]


def test_same_episode_never_leaks_and_unreviewed_cannot_train(tmp_path):
    rows=[sample(tmp_path,1,'episode'),sample(tmp_path,2,'episode')]
    result=manifest(tmp_path,rows)
    assert len({s['split'] for s in result['samples']})==1 and not result['training_ready']
    with pytest.raises(ValueError,match='review'):manifest(tmp_path,[dict(rows[0],reviewed=False)])


def test_review_box_or_episode_change_is_not_accepted(tmp_path):
    row=sample(tmp_path,1,'episode')
    with pytest.raises(ValueError,match='bind'):manifest(tmp_path,[dict(row,episode='fake')])
    with pytest.raises(ValueError,match='bind'):manifest(tmp_path,[dict(row,boxes=[])])


def test_complete_negative_needs_review_and_changed_image_refuses(tmp_path):
    row=sample(tmp_path,1,'episode');row['boxes']=[]
    proof=json.loads((tmp_path/row['proof']).read_text());proof['boxes']=[]
    (tmp_path/row['proof']).write_text(json.dumps(proof))
    assert manifest(tmp_path,[row])['samples'][0]['boxes']==[]
    with pytest.raises(ValueError):manifest(tmp_path,[dict(row,complete=False)])
    cv2.imwrite(str(tmp_path/row['frame']),np.full((32,32,3),77,dtype=np.uint8))
    with pytest.raises(ValueError,match='bind'):manifest(tmp_path,[row])


def test_export_revalidates_images_labels_and_whole_manifest(tmp_path):
    data=ready(tmp_path);out=tmp_path/'dataset'
    assert data['training_ready']
    export(tmp_path,data,out)
    assert verify_export(tmp_path,out)==data
    label=next((out/'labels').rglob('*.txt'));label.write_text('wrong label')
    with pytest.raises(ValueError,match='labels changed'):verify_export(tmp_path,out)


def test_shadow_off_never_calls_native_and_invalid_model_cannot_run(tmp_path):
    policy=tmp_path/'neural-learning.json';policy.write_text(json.dumps(dict(mode='off')))
    assert observe(SimpleNamespace(),np.zeros((32,32,3)),tmp_path)['status']=='off'
    policy.write_text(json.dumps(dict(mode='shadow')))
    with pytest.raises(ValueError,match='absent'):observe(SimpleNamespace(),np.zeros((32,32,3)),tmp_path)
