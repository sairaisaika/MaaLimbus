from pathlib import Path
import json

import cv2
import numpy as np
import pytest

from maalimbus.battle_vision import BattleCatalog,planning_anchors,preview_labels
from maalimbus.vision import Text

ROOT=Path(__file__).resolve().parents[1]


def derived_battle_frame(*,missing=False,duplicate=False,paid=False,defeat=False,after=False):
    image=np.full((720,1280,3),22,np.uint8)
    catalog=BattleCatalog(ROOT/'assets/resource/base')
    for key,x,y in [('win_rate',1120,620),('skill_slash',250,556),('skill_pierce',550,556)]:
        if missing and key!='win_rate':continue
        glyph=cv2.cvtColor(catalog.glyphs[key],cv2.COLOR_GRAY2BGR)
        h,w=glyph.shape[:2];image[y:y+h,x:x+w]=glyph
        if duplicate and key=='win_rate':image[620:620+h,1020:1020+w]=glyph
    if paid:cv2.putText(image,'Purchase Lunacy',(410,360),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    if defeat:cv2.putText(image,'DEFEAT',(490,240),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    if after:cv2.putText(image,'Neutral',(250,645),cv2.FONT_HERSHEY_SIMPLEX,.75,(255,255,255),2)
    return image


@pytest.mark.parametrize('scale', [1.,1.5])
def test_small_glyph_anchors_require_button_and_damage_bar(scale):
    image=derived_battle_frame()
    if scale!=1:image=cv2.resize(image,None,fx=scale,fy=scale)
    result=planning_anchors(image,BattleCatalog(ROOT/'assets/resource/base'))
    assert result is not None and len(result['skill_glyphs'])==2


@pytest.mark.parametrize('case', ['missing','duplicate','jp','aspect','blank'])
def test_ambiguous_or_unsupported_planning_is_refused(case):
    image=derived_battle_frame(missing=case=='missing',duplicate=case=='duplicate')
    if case=='blank':image[:]=22
    if case=='aspect':image=image[:600]
    assert planning_anchors(image,BattleCatalog(ROOT/'assets/resource/base'),'jp' if case=='jp' else 'en') is None


def test_labels_are_diagnostic_local_and_not_a_survival_authorization():
    records=[Text('Neutral',(200,580,90,25),.98),Text('Favored',(500,580,90,25),.98),
             Text('Hopeless',(200,100,90,25),.98),Text('Dominating',(700,580,90,25),.3)]
    result=preview_labels(records,(1280,720))
    assert [r['label'] for r in result]==['neutral','favored']
    assert result[0]['attention'] and not result[1]['attention']


def test_battle_task_never_submits_or_retries_turn():
    interface=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    nodes=json.loads((ROOT/'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf-8'))
    assert not next(t for t in interface['task'] if t['entry']=='BattlePlanStart')['default_check']
    assert nodes['BattlePlanOnce']['action']=='ClickKey' and nodes['BattlePlanOnce']['key']==80
    assert nodes['BattlePlanOnce']['max_hit']==1
    assert nodes['BattlePlanOnce']['next']==['BattlePlanObserve']
    assert nodes['BattlePlanBoundary']['custom_action_param']['reason']=='battle_plan_observed_turn_submission_pending'
