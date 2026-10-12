"""Teacher and Maa journal share encoded PNG hashes, not decoded pixel hashes."""
import json,shutil
from pathlib import Path
import pytest
from maalimbus.runner import pre_battle_identity_evidence
ROOT=Path(__file__).resolve().parents[1]
FRAME=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-174217/frame-0012.json'


def test_actual_native_record_reaches_independent_teacher_and_changed_bytes_refuse(tmp_path):
    if not FRAME.exists():pytest.skip('Actual local prebattle frame unavailable')
    shutil.copyfile(FRAME,tmp_path/FRAME.name)
    png=tmp_path/FRAME.with_suffix('.png').name;shutil.copyfile(FRAME.with_suffix('.png'),png)
    record=json.loads(FRAME.read_text(encoding='utf-8'))
    result=pre_battle_identity_evidence(tmp_path,record)
    assert result is not None and result['slot_states']['measured']==12
    assert len(result['resolved'])==3 and not result['detector_read']
    png.write_bytes(png.read_bytes()+b'changed')
    assert pre_battle_identity_evidence(tmp_path,record) is None
