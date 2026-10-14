from types import SimpleNamespace
import numpy as np
import pytest
from maalimbus.grace_balance_native import repair
from maalimbus.grace_vision import available_starlight
from maalimbus.vision import Text

def call(values):
    iterator=iter(values)
    def native(kind,config,image):
        assert config.only_rec is False
        value=next(iterator)
        rows=[] if value is None else [SimpleNamespace(text=str(value),score=.999)]
        return SimpleNamespace(hit=bool(rows),filtered_results=rows)
    return native

@pytest.mark.parametrize('number',[5,25,75,95,105,116,1000])
def test_independent_detected_balance_agrees_without_changing_floor(number):
    label=Text('Avallable',(1392,49,84,30),.99)
    records,proof=repair(call([number,number]),np.zeros((1080,1920,3)),[label])
    assert available_starlight(records,(1920,1080))==number
    assert len(proof)==2

@pytest.mark.parametrize('values',[[75,70],[75,None],[None,None]])
def test_missing_or_conflicting_crops_do_not_prove_number(values):
    records,_=repair(call(values),np.zeros((1080,1920,3)),[Text('Available',(1392,49,84,30),.99)])
    assert available_starlight(records,(1920,1080)) is None

def test_detection_does_not_delete_a_conflicting_fullframe_number():
    records,_=repair(call([75,75]),np.zeros((1080,1920,3)),[
        Text('Available',(1392,49,84,30),.99),Text('7',(1520,45,30,40),.95)])
    assert available_starlight(records,(1920,1080)) is None

def test_missing_label_is_zero_native_call():
    records,proof=repair(lambda *a:pytest.fail('No anchor'),np.zeros((1080,1920,3)),[])
    assert records==[] and proof==[]
