import pytest
from maalimbus.initial_transaction import InitialTransaction

def test_restart_never_repeats_pending_or_selected_gift(tmp_path):
    p=tmp_path/'initial.json';t=InitialTransaction(p)
    t.prepare('run','charge',(0,2),'frame.png')
    t.intent(1,'Employee Card',(0,2),'before.png')
    t=InitialTransaction(p)
    with pytest.raises(ValueError):t.prepare('run','charge',(0,2),'again.png')
    with pytest.raises(ValueError):t.observe((0,2),[1],'unchanged.png')
    t.observe((1,2),[1],'after.png')
    t=InitialTransaction(p)
    assert t.prepare('run','charge',(1,2),'fresh.png')['selected'][0]['title']=='Employee Card'
    with pytest.raises(ValueError):t.intent(1,'Employee Card',(1,2),'repeat.png')
    with pytest.raises(ValueError):t.prepare('run','charge',(0,2),'wrongcount.png')
