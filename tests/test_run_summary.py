import json
from pathlib import Path
import pytest
from maalimbus.run_summary import completed_hard_summary
FRAME=Path(__file__).resolve().parents[1]/'evidence/runtime/window-20261008-144554/frame-0457.json'

def test_real_hard_five_floor_summary_is_not_paid_receipt():
    summary=completed_hard_summary(json.loads(FRAME.read_text()))
    assert summary['floors']==[1,2,3,4,5] and not summary['reward_received']

@pytest.mark.parametrize('missing',['Complete','100%','Floor 5 [HARD]','Floor3','Floor4'])
def test_partial_summary_never_proves_clear(missing):
    data=json.loads(FRAME.read_text());data['ocr']=[t for t in data['ocr'] if t['text']!=missing]
    assert completed_hard_summary(data) is None

def test_changed_normal_mode_and_incomplete_floor_five_refuse():
    for pattern,replacement in [('[HARD]','[NORMAL]'),('7/7','6/7')]:
        data=json.loads(FRAME.read_text())
        for t in data['ocr']:
            if t['text']==pattern:t['text']=replacement
        assert completed_hard_summary(data) is None
