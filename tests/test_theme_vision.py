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


def test_current_floor_two_mode_and_card_titles_remain_independent():
    root=ROOT/'evidence/runtime/window-20261008-081811/frame-0001'
    image=cv2.imread(str(root)+'.png');data=json.loads(Path(str(root)+'.json').read_text())
    records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
    locale=json.loads((ROOT/'assets/resource/en/locale.json').read_text())
    cat=catalog()
    assert theme_page(image,cat,records,locale) is None # wholeOCR .827 does not pass.
    narrow=Text('HARD',(1372,48,64,38),.9999)
    assert theme_page(image,cat,records+[narrow],locale)=='hard'
    assert theme_page(image,cat,records+[Text('HARD',narrow.box,.89)],locale) is None
    assert theme_page(image,cat,records+[narrow,Text('NORMAL',narrow.box,.99)],locale) is None
    for label in ('Pack Search','Refresh','SELECT FLOOR 2 THEME PACK'):
        without=[t for t in records if t.text!=label]+[narrow]
        no_details=image.copy();no_details[308:375,500:1420]=0
        assert theme_page(no_details,cat,without,locale) is None
    cards=pack_candidates(image,records,cat)
    assert [c.name for c in cards]==[None,'Emotional Judgment','Emotional Craving']
    altered=image.copy();altered[308:375,500:1420]=0 # Remove old detail glyphs.
    cards=pack_candidates(altered,records,cat)
    assert [c.name for c in cards]==[None,'Emotional Judgment','Emotional Craving']
    assert 820<cards[1].box[0]<845 and 260<cards[1].box[1]<285
    # Without visible clips and detail glyphs, title coordinates grant no input.
    altered[250:310,500:1420]=0
    assert pack_candidates(altered,records,cat)==[]


def test_regular_battle_requires_numeric_turn_and_both_controls():
    from maalimbus.battle_vision import battle_hud
    path=ROOT/'evidence/runtime/window-20261008-084129/frame-0024.json'
    data=json.loads(path.read_text());records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
    assert battle_hud(records,data['size']) is None
    numeric=Text('1',(68,90,82,40),.9999)
    hud=battle_hud(records+[numeric],data['size'])
    assert hud and hud['wave'] is None and hud['turn']=='1'
    for missing in ('TURN','Win','Rate','Damage'):
        assert battle_hud([r for r in records if r.text!=missing]+[numeric],data['size']) is None
    assert battle_hud(records+[Text('1',numeric.box,.89)],data['size']) is None
    assert battle_hud(records+[numeric,numeric],data['size']) is None
