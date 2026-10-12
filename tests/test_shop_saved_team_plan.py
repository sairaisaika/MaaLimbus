from types import SimpleNamespace
import pytest
from maalimbus.gift_plan import shop_wanted
from maalimbus.policies import Team


def test_shop_uses_saved_two_keyword_system_and_block_wins():
    catalog=SimpleNamespace(entries={
        'Rupture Gift':dict(keywords=['Rupture']),
        'Poise Gift':dict(keywords=['Poise']),
        'Charge Gift':dict(keywords=['Charge']),
        'Explicit Gift':dict(keywords=[]),
    })
    team=Team(7,frozenset({'Poise','Rupture'}),allow=frozenset({'Explicit Gift','Rupture Gift'}),
              block=frozenset({'Rupture Gift'}))
    assert shop_wanted(team,catalog)==['Explicit Gift','Poise Gift']
    with pytest.raises(ValueError):shop_wanted(Team(7,frozenset(),allow=frozenset({'Missing'})),catalog)
