import pytest
from maalimbus.theme_transaction import ThemeTransaction
from maalimbus.map_vision import MapHeader
class Catalog:
    def identity(self,name):return name

def test_wrong_floor_or_pack_never_resolves_pending_drag(tmp_path):
    t=ThemeTransaction(tmp_path/'theme.json');t.intent('run',1,'To be Crushed','before.png')
    with pytest.raises(ValueError):t.intent('run',1,'To be Crushed','repeat.png')
    with pytest.raises(ValueError):t.observe('run',None,Catalog(),'unknown.png')
    with pytest.raises(ValueError):t.observe('run',MapHeader(2,'To be Crushed',None,None),Catalog(),'wrong.png')
    with pytest.raises(ValueError):t.observe('run',MapHeader(1,'Other',None,None),Catalog(),'other.png')
    assert t.data['pending']['name']=='To be Crushed'
    assert t.observe('run',MapHeader(1,'To be Crushed',None,None),Catalog(),'map.png')
    with pytest.raises(ValueError):t.intent('run',1,'To be Crushed','again.png')
