from dataclasses import replace
import pytest
from maalimbus.auto_formation import Identity,choose_identity


def test_highest_owned_compatible_level_wins_and_mixed_keywords_are_or():
    low=Identity('Faust','Low hybrid',45,frozenset({'Burn','Tremor'}),True,True,'frame1',(1,1,5,5))
    high=replace(low,name='High Burn',level=60,keywords=frozenset({'Burn'}))
    unowned=replace(high,name='Rental',level=70,owned=False)
    wrong=replace(high,name='Wrong sinner',sinner='Yi Sang',level=80)
    unknown=replace(high,name='Unreadable',level=None)
    assert choose_identity([low,high,unowned,wrong,unknown],'Faust',{'Burn','Tremor'},inventory_complete=True)==high
    assert choose_identity([unowned,unknown],'Faust',{'Burn'},inventory_complete=True) is None


def test_partial_inventory_is_not_highest_level_proof():
    with pytest.raises(ValueError):choose_identity([],'Faust',{'Burn'})
    assert choose_identity([],'Faust',{'Burn'},descending_level_verified=True) is None
