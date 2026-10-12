import pytest
from pathlib import Path
import json
from maalimbus.storage import write_json
from maalimbus.learning_dataset import digest
from maalimbus.owned_inventory import reconcile_titles
from maalimbus.semantic_labels import collect


@pytest.mark.parametrize('fault',[None,'image','frame','index','ownership','filter'])
def test_teacher_proposals_require_unchanged_independent_evidence(tmp_path,fault):
    index=dict(identities=[dict(id=10101,sinner_index=1,titles={'en':'LCB Sinner'},
        wiki_systems=dict(keywords=['Sinking'],unknown_keywords=[]))])
    index_path=tmp_path/'index.json';write_json(index_path,index)
    frame=tmp_path/'frame.json';image=tmp_path/'frame.png';image.write_bytes(b'unit-image-binding')
    record=dict(size=[1920,1080],image_sha256=digest(image),inventory_locale='en',
        ocr=[dict(text='IDENTITIES:YISANG',box=[178,69,208,40],score=.99)],
        owned_filter=dict(owned_checked=True,all_unchecked=True),
        inventory_observations=[dict(title='LCB Sinner',score=.99,level=10,uptie=None,
                                    evidence=dict(frame=str(frame),image_sha256=digest(image)))])
    write_json(frame,record)
    page=reconcile_titles(index,1,record['inventory_observations'],'en')
    page.update(frame=str(frame),frame_sha256=digest(frame),image_sha256=digest(image))
    state=dict(index_sha256=digest(index_path),sinners=[page],inventory_complete=False)
    if fault=='image':image.write_bytes(b'changed')
    elif fault=='frame':record['ocr']=[];write_json(frame,record)
    elif fault=='index':index['identities'][0]['titles']['en']='Different';write_json(index_path,index)
    elif fault=='ownership':page['owned']=[]
    elif fault=='filter':
        record['owned_filter']['owned_checked']=False;write_json(frame,record);page['frame_sha256']=digest(frame)
    state_path=tmp_path/'inventory.json';write_json(state_path,state)
    if fault:
        with pytest.raises(ValueError):collect(tmp_path,index_path,state_path)
    else:
        result=collect(tmp_path,index_path,state_path)
        assert result['labels'][0]['systems']==['Sinking']
        assert not result['labels'][0]['model_applied'] and not result['labels'][0]['training_eligible']


def transition_fixture(tmp_path,scenes=('MYSTERY_PAGE','RESULT_PAGE'),utc=None):
    import numpy as np,cv2
    utc=utc or ('2026-10-12T04:00:00-04:00','2026-10-12T04:00:01-04:00')
    evidence=tmp_path/'evidence';evidence.mkdir(parents=True,exist_ok=True)
    paths=[]
    for n,scene in enumerate(scenes):
        image=evidence/f'frame-{n:04d}.png'
        cv2.imwrite(str(image),np.full((12,12,3),40+n*30,np.uint8))
        frame=evidence/f'frame-{n:04d}.json'
        write_json(frame,dict(scene=scene,size=[12,12],utc=utc[n],image_sha256=digest(image)))
        paths.append((frame,image))
    observation=dict(page='UNKNOWN_PAGE',bounded=True,steps_used=1,step_limit=3,
        allowed_operations=['tap_continue'],before_frame='evidence/frame-0000.json',
        after_frame='evidence/frame-0001.json',
        action=dict(kind='tap_continue',target='continue',reason='bounded exploration',
                    expected_effect='page advances'),
        success_assertion=dict(role='success',verified=True,teacher='independent_postcondition_caption',
            postcondition='Result heading visible',evidence='evidence/frame-0001.json'))
    return observation,paths


def test_success_transition_stays_a_candidate_until_a_human_reviews_it(tmp_path):
    from maalimbus.semantic_labels import candidate_transition
    observation,_=transition_fixture(tmp_path)
    result=candidate_transition(tmp_path,'ep-1','en',observation,tmp_path/'out')
    assert result['status']=='candidate_pending_human_review'
    assert not result['promotable'] and not result['reviewed']
    assert not result['training_eligible'] and not result['production'] and not result['input_authorized']
    stored=json.loads(Path(result['candidate']).read_text(encoding='utf-8'))
    assert stored['kind']=='success_transition_candidate'
    assert stored['before']['scene']!=stored['after']['scene']
    assert stored['transition']['action']['kind']=='tap_continue'
    assert stored['exploration']==dict(allowed_operations=['tap_continue'],bounded=True,steps_used=1,step_limit=3)
    assert stored['unknown_count']>=1 and not stored['human_reviewed']
    assert digest(Path(result['candidate']))==result['candidate_sha256']


@pytest.mark.parametrize('fault',['unbounded','steps','outside_set','unverified','not_success','same_scene',
                                  'same_frame','time_order','no_page','missing_evidence'])
def test_transition_refuses_without_bounded_verified_evidence(tmp_path,fault):
    from maalimbus.semantic_labels import candidate_transition
    observation,_=transition_fixture(tmp_path)
    if fault=='unbounded':observation['bounded']=False
    elif fault=='steps':observation['steps_used']=9
    elif fault=='outside_set':observation['action']=dict(kind='tap_abyss')
    elif fault=='unverified':observation['success_assertion']['verified']=False
    elif fault=='not_success':observation['success_assertion']['role']='optimistic_guess'
    elif fault=='same_scene':
        frame=tmp_path/'evidence'/'frame-0001.json';record=json.loads(frame.read_text(encoding='utf-8'))
        record['scene']='MYSTERY_PAGE';write_json(frame,record)
    elif fault=='same_frame':observation['after_frame']='frame-0000.json'
    elif fault=='time_order':observation['before_frame'],observation['after_frame']='frame-0001.json','frame-0000.json'
    elif fault=='no_page':observation['page']=''
    else:observation['after_frame']='frame-9999.json'
    with pytest.raises(ValueError):candidate_transition(tmp_path,'ep-1','en',observation,tmp_path/'out')


def test_transition_records_every_declared_unknown_without_resolving_it(tmp_path):
    from maalimbus.semantic_labels import candidate_transition
    observation,_=transition_fixture(tmp_path)
    observation['unknowns']=[dict(kind='unmapped_button',detail='bottom-right glyph',resolved=False)]
    observation['deviations']=['dialog appeared','no currency change']
    result=candidate_transition(tmp_path,'ep-1','en',observation,tmp_path/'queue')
    stored=json.loads(Path(result['candidate']).read_text(encoding='utf-8'))
    kinds=[row['kind'] for row in stored['unknowns']]
    assert kinds==['unmapped_button','deviation','deviation']
    assert all(row['resolved'] is False for row in stored['unknowns'])
    assert stored['promotable'] is False
