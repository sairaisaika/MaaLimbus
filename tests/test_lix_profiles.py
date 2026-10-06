from dataclasses import replace
import pytest
from maalimbus.lix_profiles import import_profiles
from maalimbus.policies import Team
from maalimbus.storage import ProfileStore,SINNERS


def fixture():
    return dict(team_indexes=[5,1],mirror_team_styles=['Poise','Burn+Tremor'],
        mirror_team_ego_gift_styles=[['Poise'],['Burn','Tremor']],team_orders=[list(SINNERS),list(reversed(SINNERS))],
        mirror_team_stars=[['1','3','4','6'],['0+','7++']],mirror_team_initial_ego_orders=[[1,2,3],[3,2,1]],
        mirror_team_ego_allow_list=[[],['Good']],mirror_team_ego_block_list=[[],['Bad']])


def test_lix_columns_import_in_rotation_order_preserve_other_preferences(tmp_path):
    existing=Team(1,frozenset(),name='My saved team',pack_weights=(('Existing',37),))
    teams=import_profiles(fixture(),(existing,Team(9,frozenset())))
    assert [t.slot for t in teams]==[5,1,9]
    assert teams[1].formation_keywords=={'Burn','Tremor'}
    assert teams[1].name==existing.name and teams[1].pack_weights==existing.pack_weights
    assert teams[0].graces==('1','3','4','6') and not teams[0].auto_team
    store=ProfileStore(tmp_path/'profiles.json'); assert store.save(teams)==teams


@pytest.mark.parametrize('change',[
    {'team_indexes':[1,1]}, {'team_orders':[list(SINNERS)]},
    {'mirror_team_styles':['Poise','Unknown']}, {'mirror_team_stars':[['1','1+'],[]]},
    {'mirror_team_stars':[['10'],[]]}, {'mirror_team_stars':[[1],[]]},
])
def test_malformed_import_cannot_overwrite_profiles(change):
    with pytest.raises(ValueError):import_profiles({**fixture(),**change})
