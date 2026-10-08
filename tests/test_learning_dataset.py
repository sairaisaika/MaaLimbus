import hashlib
import json
import pytest
from maalimbus.learning_dataset import manifest


def sample(root,name='frame',episode='real-run',label='MAP'):
    image=root/(name+'.png');image.write_bytes(name.encode())
    proof=root/(name+'.json');proof.write_text(json.dumps({'actual_image_sha256':hashlib.sha256(image.read_bytes()).hexdigest()}))
    return dict(frame=image.name,proof=proof.name,reviewed=True,episode=episode,label=label)


def test_adjacent_frames_from_one_run_cannot_leak_between_splits(tmp_path):
    rows=[sample(tmp_path,'one'),sample(tmp_path,'two')]
    result=manifest(tmp_path,rows)
    assert len({s['split'] for s in result['samples']})==1
    assert not result['training_ready'] and not result['model_trained']
    assert not result['production_enabled'] and not result['input_authorized']


def test_predicted_ocr_labels_cannot_be_used_as_verified_truth(tmp_path):
    row=sample(tmp_path);row['reviewed']=False
    with pytest.raises(ValueError,match='reviewed'):manifest(tmp_path,[row])


def test_changed_image_and_conflicting_duplicate_are_rejected(tmp_path):
    row=sample(tmp_path)
    with pytest.raises(ValueError,match='duplicate'):manifest(tmp_path,[row,dict(row,episode='other-run')])
    (tmp_path/row['frame']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='bind'):manifest(tmp_path,[row])


def test_missing_or_external_evidence_is_not_silently_skipped(tmp_path):
    row=sample(tmp_path);row['frame']='../outside.png'
    with pytest.raises(ValueError,match='outside'):manifest(tmp_path,[row])
    row['frame']='missing.png'
    with pytest.raises(ValueError,match='missing'):manifest(tmp_path,[row])
