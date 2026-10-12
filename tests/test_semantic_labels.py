import pytest
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
