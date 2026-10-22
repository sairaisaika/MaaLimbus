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


def test_a_changed_keyword_is_a_preference_not_a_promise(tmp_path):
    """A resumed scope may name a wider team ("charge" -> "charge+tremor"); that is not a stop."""
    from maalimbus.initial_transaction import InitialTransaction
    path = tmp_path / 'tx.json'
    first = InitialTransaction(path)
    first.prepare('scope', 'charge', [0], 'proof-1')
    again = InitialTransaction(path)
    data = again.prepare('scope', 'charge+tremor', [0], 'proof-2')
    assert data['keyword'] == 'charge+tremor'
    assert data['keyword_history'] == ['charge']


def test_a_pending_gift_still_refuses_a_changed_keyword(tmp_path):
    from maalimbus.initial_transaction import InitialTransaction
    path = tmp_path / 'tx.json'
    first = InitialTransaction(path)
    data = first.prepare('scope', 'charge', [0], 'proof-1')
    data['pending'] = {'name': 'Charged Battery'}
    path.write_text(__import__('json').dumps(data), encoding='utf-8')
    again = InitialTransaction(path)
    with pytest.raises(ValueError):
        again.prepare('scope', 'charge+tremor', [0], 'proof-2')
