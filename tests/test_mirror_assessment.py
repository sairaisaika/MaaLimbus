import json,shutil
from pathlib import Path
import pytest
from maalimbus.storage import read_json,write_json
from maalimbus.mirror_assessment import assess
ROOT=Path(__file__).resolve().parents[1]


def retained(tmp_path):
    path=ROOT/'build/team-seven-floor-five-real-verification.json'
    if not path.exists():pytest.skip('Private retained native proof absent')
    proof=read_json(path)
    for item in proof['proofs']:
        source=Path(item['frame']);shutil.copy2(source,tmp_path/source.name)
        shutil.copy2(source.with_suffix('.png'),tmp_path/source.with_suffix('.png').name)
        item['frame']=source.name
    run=dict(id=proof['scope'],team=proof['team'],floors=[1,2,3,4,5],victory=True,reward=False)
    write_json(tmp_path/'proof.json',proof);write_json(tmp_path/'ledger.json',dict(active=run))
    return proof,run


def test_actual_unpaid_run_scores_completion_without_claiming_quality_or_receipt(tmp_path):
    retained(tmp_path)
    original={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    score=assess(tmp_path,'ledger.json','proof.json')
    assert score['progression_score']==90 and score['censored']
    assert score['efficiency_score'] is None and score['survival_score'] is None
    assert not score['components']['reward_verified'] and not score['strategy_training_eligible']
    assert original=={p.name:p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('fault',['scope','summary','png','reward_flag'])
def test_scope_image_and_summary_cannot_fake_a_score(tmp_path,fault):
    proof,run=retained(tmp_path)
    if fault=='scope':proof['scope']='other'
    elif fault=='summary':proof['summary']['progress']=99
    elif fault=='png':next(tmp_path.glob('*.png')).write_bytes(b'altered')
    else:run['reward']=True
    write_json(tmp_path/'proof.json',proof);write_json(tmp_path/'ledger.json',dict(active=run))
    if fault=='reward_flag':
        assert not assess(tmp_path,'ledger.json','proof.json')['components']['reward_verified']
    else:
        with pytest.raises(ValueError):assess(tmp_path,'ledger.json','proof.json')
