import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from maalimbus.policies import Team
from maalimbus.storage import ProfileStore,team_from_json
from maalimbus.theme_vision import ThemeCatalog,theme_page,pack_candidates,recommend_pack
from maalimbus.vision import Text

ROOT=Path(__file__).resolve().parents[1]


def catalog():return ThemeCatalog(ROOT/'assets/resource/base')


def frame(*,normal=False,new=False):
    cat=catalog()
    image=np.random.default_rng(7).integers(0,120,(720,1280,3),dtype=np.uint8)
    def paste(key,x,y):
        icon=cv2.cvtColor(cat.glyphs[key],cv2.COLOR_GRAY2BGR)
        image[y:y+icon.shape[0],x:x+icon.shape[1]]=icon
    paste('normal_mode' if normal else 'hard_mode',830,25)
    paste('pack_search',1060,40)
    for x in (252,652):paste('theme_pack_detail',x,203)
    if new:paste('mirror_theme_pack_new',140,190)
    records=[Text('ASEA',(145,445,65,20),.99),Text('Automated Factory',(540,445,155,20),.99)]
    return image,records


def test_stable_glyphs_titles_weights_and_new_marker():
    cat=catalog();image,records=frame()
    assert theme_page(image,cat)=='hard'
    candidates=pack_candidates(image,records,cat)
    assert [c.name for c in candidates]==['ASEA','Automated Factory']
    team=Team(1,frozenset(),pack_weights=(('ASEA',1),('Automated Factory',20)))
    target,ranking=recommend_pack(candidates,team)
    assert target['name']=='Automated Factory' and ranking[1]['weight']==1
    padded=[Text('ASEA',(130,436,166,57),.99),records[1]]
    assert pack_candidates(image,padded,cat)[0].name=='ASEA'
    new_image,_=frame(new=True)
    candidates=pack_candidates(new_image,records,cat)
    assert candidates[0].new and recommend_pack(candidates,Team(1,frozenset()))[0]['name']=='Automated Factory'


def test_normal_unknown_duplicate_spilled_and_low_confidence():
    cat=catalog();image,records=frame(normal=True)
    assert theme_page(image,cat)=='normal'
    assert theme_page(np.zeros_like(image),cat) is None
    assert recommend_pack(pack_candidates(image,[],cat),Team(1,frozenset()))==(None,[])
    duplicate=[records[0],Text('ASEA',(550,445,65,20),.99)]
    assert pack_candidates(image,duplicate,cat)==[]
    spill=[Text('ASEA',(110,445,110,20),.99),Text('Automated Factory',(540,445,155,20),.7)]
    assert all(c.name is None for c in pack_candidates(image,spill,cat))
    assert recommend_pack(pack_candidates(image,records,cat),Team(1,frozenset(),pack_weights=(('ASEA',0),('Automated Factory',0))))==(None,[])


def test_scaled_geometry_and_changed_artwork():
    cat=catalog();image,records=frame()
    scaled=cv2.resize(image,(1920,1080))
    records=[Text(t.text,tuple(round(v*1.5) for v in t.box),t.score) for t in records]
    assert theme_page(scaled,cat)=='hard'
    assert [c.name for c in pack_candidates(scaled,records,cat)]==['ASEA','Automated Factory']


def test_profiles_retain_pack_weights_and_old_profiles(tmp_path):
    team=Team(1,frozenset(),pack_weights=(('ASEA',20),('Automated Factory',0)))
    store=ProfileStore(tmp_path/'profiles.json')
    assert store.save([team])==(team,) and ProfileStore(store.path).load()==(team,)
    assert team_from_json({'slot':2}).pack_weights==()


@pytest.mark.parametrize('weights',[(('ASEA',True),),(('ASEA',-1),),(('ASEA',101),),
                                   (('ASEA',1),('ASEA',20)),(('',10),)])
def test_invalid_weights_refused(weights):
    with pytest.raises(ValueError):Team(1,frozenset(),pack_weights=weights)


def test_catalog_checks_glyph_hashes(tmp_path):
    data=json.loads((ROOT/'assets/resource/base/theme-catalog.json').read_text(encoding='utf-8'))
    data['glyphs']={'hard_mode':dict(path='../outside.png',sha256='fake')}
    (tmp_path/'theme-catalog.json').write_text(json.dumps(data))
    with pytest.raises(ValueError):ThemeCatalog(tmp_path)
