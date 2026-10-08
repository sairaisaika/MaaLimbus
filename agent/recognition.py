import hashlib
import json
import os
import random
import time
import traceback
from datetime import datetime, timezone
from dataclasses import replace
from functools import wraps
from pathlib import Path
from types import SimpleNamespace

import cv2
from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from maa.pipeline import JOCR, JRecognitionType, JTemplateMatch
from maa.toolkit import Toolkit

from maalimbus.vision import Text, classify, find, inset_box
from maalimbus.policies import Team
from maalimbus.team_vision import team_row, team_header
from maalimbus.windows_preflight import check_window, InputPermissionError
from maalimbus.adb_preflight import controller_foreground
from maalimbus.storage import ProfileStore
from maalimbus.controller_lease import ControllerLease
from maalimbus.gift_vision import GiftCatalog, floor_candidates, recommend,search_owned_names
from maalimbus.jobs import wait_job
from maalimbus import runner
from maalimbus.runtime_paths import ROOT
from maalimbus.theme_vision import ThemeCatalog, theme_page, pack_candidates, recommend_pack
from maalimbus.deployment import deployment_page,observe_deployment,next_sinner,target_box,badge_rois,DeploymentDraft
from maalimbus.storage import KEYWORDS, SINNERS
from maalimbus.battle_vision import BattleCatalog,planning_anchors,preview_labels,battle_hud,auto_assign_plan,auto_assign_buttons,begin_turn_plan,start_button
from maalimbus import star_vision
from maalimbus import initial_gifts
from maalimbus.map_vision import map_header, route_decision, node_panel, pre_battle_team_page
from maalimbus.storage import read_json, write_json
from maalimbus.storage import RunStore


def guarded_callback(failed_result):
    """Never let Python exceptions become undefined Maa C callback returns.

    A fault latches this Agent instance closed, including recognition alternatives.
    Journal failures cannot undo the latch or escape the callback boundary.
    """
    def decorate(callback):
        @wraps(callback)
        def guarded(self, context, argv):
            recognition = self if callback.__name__ == 'analyze' else self.recognition
            if getattr(recognition, 'callback_failure', None) is not None:
                return failed_result
            try:
                return callback(self, context, argv)
            except Exception as error:
                failure = dict(callback=type(self).__name__,
                    node=getattr(argv, 'node_name', ''), error_type=type(error).__name__,
                    verified_clear=False)
                recognition.callback_failure = failure
                try:
                    recognition.journal.record('callback_failed', **failure)
                except Exception:
                    # Retain the failure in memory even when the evidence disk fails.
                    failure['journal_failed'] = True
                return failed_result
        return guarded
    return decorate


class Journal:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.index = 0

    def record(self, event, **details):
        data = {'event': event, 'utc': datetime.now(timezone.utc).isoformat(), **details}
        with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as file:
            file.write(json.dumps(data, ensure_ascii=False) + '\n')

    def frame(self, frame, records, scene, **extra):
        self.index += 1
        name = f'frame-{self.index:04d}'
        if not cv2.imwrite(str(self.directory / (name + '.png')), frame):
            raise OSError('Evidence screenshot could not be saved')
        data = {'scene': scene, 'size': [frame.shape[1], frame.shape[0]],
                'utc': datetime.now(timezone.utc).isoformat(),
                'image_sha256': hashlib.sha256((self.directory/(name+'.png')).read_bytes()).hexdigest(),
                'ocr': [{'text': t.text, 'score': t.score, 'box': t.box} for t in records],**extra}
        (self.directory / (name + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return name


class LimbusRecognition(CustomRecognition):
    def __init__(self, locale='en', journal=None):
        super().__init__()
        self.locale = json.loads((ROOT / f'assets/resource/{locale}/locale.json').read_text(encoding='utf-8'))
        self.journal = journal or Journal(os.environ.get('MAALIMBUS_EVIDENCE', ROOT / 'evidence/runtime/agent'))
        self.cache = None
        self.last_frame = None
        self.last_scene = None
        self.team = None
        self.locale_name = locale
        self.scroll_count = 0
        self.scroll_hash = None
        self.gifts = None
        self.themes = None
        self.pending_pack = ''
        self.deployment_pending = None
        self.deployment_draft = None
        self.battle = None
        self.battle_before = None
        self.callback_failure = None
        self.input_validator = None
        self.star_pending = None

    def theme_catalog(self):
        if self.themes is None:
            self.themes=ThemeCatalog(ROOT/'assets/resource/base')
        return self.themes

    def gift_catalog(self):
        if self.gifts is None:self.gifts=GiftCatalog(ROOT/'assets/resource/base')
        return self.gifts

    def battle_catalog(self):
        if self.battle is None:self.battle=BattleCatalog(ROOT/'assets/resource/base')
        return self.battle

    def observe(self, context, image):
        digest = hashlib.sha256(image.tobytes()).hexdigest()
        if self.cache and self.cache[0] == digest:
            return self.cache[1:]
        detail = context.run_recognition_direct(JRecognitionType.OCR, JOCR(threshold=.2), image)
        if detail is None:
            raise RuntimeError('Maa OCR did not return evidence')
        records = []
        for result in detail.all_results:
            if hasattr(result, 'text'):
                b = result.box
                box = (b.x, b.y, b.w, b.h) if hasattr(b, 'x') else tuple(b)
                records.append(Text(result.text, box, result.score))
        size = (image.shape[1], image.shape[0])
        # Android outlined yellow menu text is missed by full-frame detection.
        # Only consult this stable local label after an independent Inferno title.
        if find(records, self.locale['inferno'], (.70,.07,.99,.3), size):
            w,h=size
            roi=[round(.315*w),round(.442*h),round(.077*w),round(.028*h)]
            detail=context.run_recognition_direct(JRecognitionType.OCR,
                JOCR(roi=roi,only_rec=True,threshold=.8),image)
            if detail is not None:
                for result in detail.all_results:
                    if hasattr(result,'text'):
                        b=result.box
                        box=(b.x,b.y,b.w,b.h) if hasattr(b,'x') else tuple(b)
                        records.append(Text(result.text,box,result.score))
        scene = classify(records, self.locale, size)
        if scene in ('UNKNOWN','BATTLE_HUD') and len(find(records,r'^TURN$',(.0,.06,.06,.13),size,.9))==1 and auto_assign_buttons(records,size) is not None:
            w,h=size;roi=(round(68*w/1920),round(90*h/1080),round(82*w/1920),round(40*h/1080))
            detail=context.run_recognition_direct(JRecognitionType.OCR,
                JOCR(roi=roi,only_rec=True,expected=[r'^\d{1,3}$'],threshold=.9),image)
            if detail is not None and detail.hit:
                x,y,rw,rh=roi
                records=[t for t in records if not (x<=t.box[0]+t.box[2]/2<=x+rw and y<=t.box[1]+t.box[3]/2<=y+rh)]
                for result in detail.filtered_results:records.append(Text(result.text,roi,result.score))
        from maalimbus.theme_vision import selection_floor
        if scene=='UNKNOWN' and selection_floor(records,size) is not None:
            # Decorations beside HARD confuse the detector. Independent page
            # controls gate a narrow recognizer; unchanged .9 confidence gate.
            w,h=size;roi=(round(1372*w/1920),round(48*h/1080),round(64*w/1920),round(38*h/1080))
            detail=context.run_recognition_direct(JRecognitionType.OCR,
                JOCR(roi=roi,only_rec=True,expected=[r'^HARD$'],threshold=.9),image)
            if detail is not None and detail.hit:
                records=[t for t in records if not (t.text.strip()=='HARD'
                         and .61<=(t.box[0]+t.box[2]/2)/w<=.83
                         and 0<=(t.box[1]+t.box[3]/2)/h<=.13)]
                for result in detail.filtered_results:
                    records.append(Text(result.text,roi,result.score))
        if scene=='UNKNOWN' and initial_gifts.page(records,size,self.locale):
            scene='INITIAL_GIFTS'
        if scene=='UNKNOWN' and star_vision.page(records,size,self.locale) and star_vision.grid(image):
            scene='STAR_GRACES'
        if scene=='UNKNOWN' and deployment_page(records,self.locale,(image.shape[1],image.shape[0])):
            scene='DEPLOYMENT'
        local=[]
        if scene=='DEPLOYMENT':
            # Isolated ordinal digits are often absent from the full-frame text
            # detector. Recognize only the small badge strips, retaining ROIs.
            for sinner,roi in badge_rois((image.shape[1],image.shape[0])).items():
                detail=context.run_recognition_direct(JRecognitionType.OCR,
                    JOCR(roi=roi,only_rec=True,expected=[r'^\s*(?:[1-9]|1[0-2])\s*$'],threshold=.85),image)
                if detail is None:raise RuntimeError('Maa local deployment OCR did not return evidence')
                x,y,w,h=roi
                records=[t for t in records if not (x<=t.box[0]+t.box[2]/2<=x+w and y<=t.box[1]+t.box[3]/2<=y+h)]
                found=[]
                if detail.hit:
                    for result in detail.all_results:
                        if hasattr(result,'text'):
                            b=result.box;box=(b.x,b.y,b.w,b.h) if hasattr(b,'x') else tuple(b)
                            records.append(Text(result.text,box,result.score))
                            found.append(dict(text=result.text,score=result.score,box=box))
                local.append(dict(sinner=sinner,roi=roi,only_rec=True,results=found))
        if scene=='UNKNOWN' and theme_page(image,self.theme_catalog(),records,self.locale):
            scene='THEME_PACKS'
        if scene=='UNKNOWN':
            if selection_floor(records,size) is not None:
                scene='THEME_PACKS' # Page identity only; mode/action gates remain.
        if scene=='UNKNOWN' and node_panel(records,size) is not None:
            # A click on the map opens this node info panel. It is judged before the
            # map on purpose: the panel leaves the floor header readable behind it, so
            # MAP would otherwise swallow the panel and the click that opened it would
            # look like a no-op (evidence/runtime/window-20261006-041345/frame-0002.json).
            scene='NODE_PANEL'
        if scene=='UNKNOWN' and map_header(records,size) is not None:
            # The floor header plus its pack line is the only map identity anchor;
            # artwork, currency and season icons are never consulted.
            scene='MAP'
        if scene in ('UNKNOWN','TEAM_LIBRARY') and pre_battle_team_page(records,size) is not None:
            # Reached from the node panel's Enter: the pre-battle team/identity page
            # carries its own `Clear Selection` and `Battle!` actions, so the generic
            # team-library judgement above is corrected only with both captions.
            scene='PRE_BATTLE_TEAM'
        if scene=='PRE_BATTLE_TEAM':
            # Full-screen detection dropped the numerator in actual 1/12.
            # Recognize only the fixed counter within an independently proven page.
            roi=(1700,754,128,58)
            detail=context.run_recognition_direct(JRecognitionType.OCR,
                JOCR(roi=roi,only_rec=True,expected=[r'^\d{1,2}\s*/\s*\d{1,2}$'],threshold=.85),image)
            if detail is None:raise RuntimeError('Maa local participant OCR returned no evidence')
            x,y,w,h=roi
            records=[t for t in records if not (x<=t.box[0]+t.box[2]/2<=x+w and y<=t.box[1]+t.box[3]/2<=y+h)]
            found=[]
            if detail.hit:
                for result in detail.filtered_results:
                    records.append(Text(result.text,roi,result.score))
                    found.append(dict(text=result.text,score=result.score,box=list(roi)))
            local.append(dict(purpose='deployment_participants',roi=list(roi),only_rec=True,results=found))
        if scene=='UNKNOWN' and battle_hud(records,size) is not None:
            # The combat HUD's own WAVE/TURN captions; a battle is never inferred
            # from artwork, and this identifies the page only.
            scene='BATTLE_HUD'
        if scene=='UNKNOWN' and planning_anchors(image,self.battle_catalog(),self.locale_name):
            scene='BATTLE_PLANNING'
        if scene in ('STAR_GRACES','STAR_CONFIRM'):
            # The full text detector truncated 86 to 8 in actual frame-0005.
            # A fixed numeric crop is accepted only with a fresh Available label.
            if len(find(records,r'^Available$',(.70,.02,.80,.10),size,.85))==1:
                roi=(1515,45,54,40)
                detail=context.run_recognition_direct(JRecognitionType.OCR,
                    JOCR(roi=roi,only_rec=True,expected=[r'^\d{1,5}$'],threshold=.85),image)
                if detail is None:raise RuntimeError('Maa local Available OCR returned no evidence')
                x,y,w,h=roi
                records=[t for t in records if not (x<=t.box[0]+t.box[2]/2<=x+w and y<=t.box[1]+t.box[3]/2<=y+h)]
                found=[]
                if detail.hit:
                    for result in detail.filtered_results:
                        records.append(Text(result.text,roi,result.score))
                        found.append(dict(text=result.text,score=result.score,box=list(roi)))
                local.append(dict(purpose='available_starlight',roi=list(roi),only_rec=True,results=found))
        if scene=='STAR_CONFIRM':
            roi=(1318,459,66,45)
            detail=context.run_recognition_direct(JRecognitionType.OCR,
                JOCR(roi=roi,only_rec=True,expected=[r'^\d{1,4}$'],threshold=.85),image)
            if detail is None:raise RuntimeError('Maa local conversion cost OCR returned no evidence')
            x,y,w,h=roi
            records=[t for t in records if not (x<=t.box[0]+t.box[2]/2<=x+w and y<=t.box[1]+t.box[3]/2<=y+h)]
            found=[]
            if detail.hit:
                for result in detail.filtered_results:
                    records.append(Text(result.text,roi,result.score))
                    found.append(dict(text=result.text,score=result.score,box=list(roi)))
            local.append(dict(purpose='star_conversion_cost',roi=list(roi),only_rec=True,results=found))
        if scene=='STAR_GRACES':
            boxes=star_vision.grid(image)
            if boxes is not None:
                for box in boxes:
                    roi=star_vision.cost_roi(box)
                    detail=context.run_recognition_direct(JRecognitionType.OCR,
                        JOCR(roi=roi,only_rec=True,expected=[r'^\d{1,3}$'],threshold=.85),image)
                    if detail is None:raise RuntimeError('Maa local grace cost OCR returned no evidence')
                    found=[]
                    if detail.hit:
                        for result in detail.filtered_results:
                            if hasattr(result,'text'):
                                # This box is the requested crop, not an invented
                                # character box; retain native confidence and ROI.
                                records.append(Text(result.text,tuple(roi),result.score))
                                found.append(dict(text=result.text,score=result.score,box=list(roi)))
                    local.append(dict(purpose='grace_cost',roi=list(roi),only_rec=True,results=found))
        name = self.journal.frame(image, records, scene,local_ocr=local)
        self.last_frame, self.last_scene = image.copy(), scene
        self.cache = (digest, records, scene, name)
        return records, scene, name

    @guarded_callback(None)
    def analyze(self, context, argv):
        params = json.loads(argv.custom_recognition_param or '{}')
        records, scene, frame = self.observe(context, argv.image)
        expected = params['scene']
        if scene != expected:
            return None
        mode = params.get('team_mode')
        if params.get('initial_mode')=='confirm_forgo':
            data=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))
            path=data/'initial-gift-progress.json';progress=read_json(path)
            if (not progress.get('search_refuse_pending') or progress.get('search_confirm_pending')
                or progress['search_refuse_pending'].get('extra_starlight_spent')!=0
                or progress.get('receipt_pending') or progress.get('acknowledged')!=progress['selected']):return None
            matches=find(records,self.locale['gift_confirm'],(.53,.65,.68,.73),
                         (argv.image.shape[1],argv.image.shape[0]),.85)
            if len(matches)!=1:return None
            progress['search_confirm_pending']=dict(frame=str(self.journal.directory/(frame+'.png')),
                                                    extra_starlight_spent=0)
            write_json(path,progress)
            self.journal.record('extra_gift_forgo_intent',**progress['search_confirm_pending'],verified_clear=False)
            box,delay=inset_box(matches[0].box),random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
        elif params.get('initial_mode')=='refuse_search':
            data=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))
            path=data/'initial-gift-progress.json';progress=read_json(path)
            size=(argv.image.shape[1],argv.image.shape[0])
            if (progress.get('receipt_pending') or progress.get('search_refuse_pending')
                or progress.get('acknowledged')!=progress['selected']
                or initial_gifts.counter(records,size)!=(0,3)):return None
            if not find(records,r'^Owned$',(.64,.02,.73,.09),size,.9):return None
            matches=find(records,self.locale['initial_refuse'],(.65,.76,.78,.86),size,.85)
            if len(matches)!=1:return None
            progress['search_refuse_pending']=dict(frame=str(self.journal.directory/(frame+'.png')),
                                                   extra_starlight_spent=0)
            write_json(path,progress)
            self.journal.record('extra_gift_refuse_intent',**progress['search_refuse_pending'],verified_clear=False)
            box,delay=inset_box(matches[0].box),random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
        elif params.get('initial_mode')=='receipt':
            data=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))
            path=data/'initial-gift-progress.json';progress=read_json(path)
            if progress.get('receipt_pending'):raise ValueError('Unverified gift acknowledgement pending')
            if not progress.get('commit_pending') or progress.get('pending') is not None:return None
            titles=initial_gifts.proven_titles(progress,ROOT/'evidence/runtime')
            acknowledged=progress.get('acknowledged',[])
            if acknowledged!=progress['selected'][:len(acknowledged)] or len(acknowledged)>=len(titles):return None
            current=initial_gifts.receipt_name(records,(argv.image.shape[1],argv.image.shape[0]))
            index=len(acknowledged)
            if not initial_gifts.same_name(current,titles[index]):return None
            matches=find(records,self.locale['gift_confirm'],(.44,.70,.58,.78),
                         (argv.image.shape[1],argv.image.shape[0]),.85)
            if len(matches)!=1:return None
            progress['receipt_pending']=dict(choice=progress['selected'][index],title=titles[index],
                frame=str(self.journal.directory/(frame+'.png')))
            write_json(path,progress)
            self.journal.record('initial_receipt_ack_intent',**progress['receipt_pending'],verified_clear=False)
            box,delay=inset_box(matches[0].box),random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
        elif params.get('initial_mode')=='commit':
            data=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))
            path=data/'initial-gift-progress.json';progress=read_json(path)
            teams=ProfileStore(data/'user-team-profiles.json').load()
            team=next((t for t in teams if t.slot==params.get('slot')),None)
            size=(argv.image.shape[1],argv.image.shape[0]);count=initial_gifts.counter(records,size)
            if (team is None or count is None or count[0]!=count[1] or progress.get('pending') is not None
                or progress.get('commit_pending') or progress['selected']!=list(team.initial_gifts[:count[1]])
                or initial_gifts.selected_rows(argv.image)!=sorted(progress['selected'])):return None
            matches=find(records,r'^Select$',(.78,.76,.86,.86),size,.85)
            if len(matches)!=1:return None
            progress['commit_pending']=dict(frame=frame,selected=progress['selected'],count=count)
            write_json(path,progress)
            self.journal.record('initial_gift_commit_intent',**progress['commit_pending'],verified_clear=False)
            box,delay=inset_box(matches[0].box),random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
        elif params.get('initial_mode')=='pick':
            data=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))
            progress_path=data/'initial-gift-progress.json'
            progress=read_json(progress_path) if progress_path.exists() else {'selected':[],'pending':None}
            if progress['pending'] is not None:raise ValueError('Unverified initial gift input pending')
            teams=ProfileStore(data/'user-team-profiles.json').load()
            team=next((t for t in teams if t.slot==params.get('slot')),None)
            count=initial_gifts.counter(records,(argv.image.shape[1],argv.image.shape[0]))
            if team is None or count is None or count[0]!=len(progress['selected']) or count[0]>=count[1]:return None
            if len(team.formation_keywords)!=1:return None
            keyword=next(iter(team.formation_keywords))
            if not find(records,r'\b'+keyword+r'\b',(.675,.34,.92,.59),
                        (argv.image.shape[1],argv.image.shape[0]),.75):return None
            remaining=[g for g in team.initial_gifts if g not in progress['selected']]
            if not remaining:return None
            targets=[initial_gifts.row_target(records,(argv.image.shape[1],argv.image.shape[0]),g) for g in (1,2,3)]
            if any(t is None for t in targets):return None
            choice=remaining[0];box,title=targets[choice-1]
            progress['pending']=dict(choice=choice,title=title,count_before=count[0],capacity=count[1],frame=frame)
            write_json(progress_path,progress)
            self.journal.record('initial_gift_pick_intent',**progress['pending'],verified_clear=False)
            delay=random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
        elif params.get('initial_mode')=='group':
            if initial_gifts.counter(records,(argv.image.shape[1],argv.image.shape[0]))!=(0,2):return None
            teams=ProfileStore(Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))/'user-team-profiles.json').load()
            team=next((t for t in teams if t.slot==params.get('slot')),None)
            if team is None or len(team.formation_keywords)!=1:return None
            keyword=next(iter(team.formation_keywords))
            box=initial_gifts.group_target(records,(argv.image.shape[1],argv.image.shape[0]),keyword)
            if box is None:return None
            delay=random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
            self.journal.record('initial_gift_group_intent',frame=frame,slot=team.slot,keyword=keyword,
                                selected_count=0,verified_clear=False)
        elif params.get('star_mode')=='select_once':
            settings=read_json(Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))/'user-mirror-settings.json')
            selected=settings.get('graces')
            if (settings.get('enhance') is not False or not isinstance(selected,list)
                or not selected or any(not isinstance(g,str) or len(g)!=1 or g not in '0123456789' for g in selected)
                or len(set(selected))!=len(selected) or type(settings.get('max_starlight'))is not int):
                raise ValueError('Explicit base grace choices and budget required')
            progress_path=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))/'star-selection-progress.json'
            progress=read_json(progress_path) if progress_path.exists() else {'selected':[],'pending':None}
            if progress['pending'] is not None:raise ValueError('Unverified star input remains pending; do not repeat it')
            if any(g not in selected for g in progress['selected']):raise ValueError('Star configuration changed during selection')
            remaining=[g for g in selected if g not in progress['selected']]
            if not remaining:return None
            boxes=star_vision.grid(argv.image)
            if boxes is None:return None
            costs={g:self.read_number(context,argv.image,star_vision.cost_roi(boxes[int(g)])) for g in selected}
            available=self.read_number(context,argv.image,(1515,45,54,40))
            if any(c is None or c<=0 for c in costs.values()) or available is None:return None
            total=sum(costs.values())
            if total>settings['max_starlight'] or sum(costs[g] for g in remaining)>available:return None
            if progress.get('available_after',available)!=available:raise ValueError('Observed star balance changed outside verified selection')
            choice=remaining[0]
            pending=dict(choice=choice,cost=costs[choice],available_before=available,
                budget=settings['max_starlight'],all_costs=costs,frame=frame)
            progress['pending']=pending
            write_json(progress_path,progress)
            self.star_pending=(progress_path,pending)
            self.journal.record('star_selection_intent',**pending,enhance=False)
            box=star_vision.target_box(boxes[int(choice)])
            delay=random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
        elif params.get('star_mode')=='enter':
            data=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))
            settings=read_json(data/'user-mirror-settings.json')
            progress_path=data/'star-selection-progress.json'
            progress=read_json(progress_path)
            graces=settings.get('graces')
            if (not isinstance(graces,list) or not graces
                or any(not isinstance(g,str) or len(g)!=1 or g not in '0123456789' for g in graces)
                or len(set(graces))!=len(graces)
                or settings.get('enhance') is not False or progress.get('pending') is not None
                or progress.get('entry_pending') or progress.get('selected')!=settings.get('graces')):
                return None
            boxes=star_vision.grid(argv.image)
            if boxes is None:return None
            costs=[self.read_number(context,argv.image,star_vision.cost_roi(boxes[int(g)]))
                   for g in settings['graces']]
            available=self.read_number(context,argv.image,(1515,45,54,40))
            if (any(c is None or c<=0 for c in costs) or type(settings.get('max_starlight')) is not int
                or sum(costs)>settings['max_starlight'] or available!=progress.get('available_after')):
                return None
            matches=find(records,self.locale['enter'],(.88,.89,.99,.98),
                         (argv.image.shape[1],argv.image.shape[0]),.85)
            if len(matches)!=1:return None
            progress['entry_pending']=dict(frame=frame,choices=settings['graces'],cost=sum(costs))
            write_json(progress_path,progress)
            self.journal.record('star_entry_intent',**progress['entry_pending'],enhance=False,
                                verified_clear=False)
            box,delay=inset_box(matches[0].box),random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
        elif params.get('star_mode') in ('disable_conversion','confirm'):
            data=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))
            settings=read_json(data/'user-mirror-settings.json')
            progress=read_json(data/'star-selection-progress.json')
            if (settings.get('convert_remaining_starlight') is not False
                or progress.get('pending') is not None or not progress.get('entry_pending')
                or progress.get('selected')!=settings.get('graces')
                or progress.get('confirmation_pending')):return None
            confirming=params['star_mode']=='confirm'
            template='navigation/star-convert-unchecked.png' if confirming else 'navigation/star-convert-checked.png'
            detail=context.run_recognition_direct(JRecognitionType.TemplateMatch,
                JTemplateMatch(template=[template],roi=(1065,523,49,49),
                               threshold=[.95]),argv.image)
            if detail is None or not detail.hit or len(detail.filtered_results)!=1:return None
            b=detail.filtered_results[0].box
            box=inset_box((b.x,b.y,b.w,b.h) if hasattr(b,'x') else tuple(b))
            if confirming:
                remaining=self.read_number(context,argv.image,(1063,459,46,45))
                converted=self.read_number(context,argv.image,(1318,459,66,45))
                if remaining!=progress.get('available_after') or converted!=0:return None
                matches=find(records,self.locale['gift_confirm'],(.51,.71,.65,.77),
                    (argv.image.shape[1],argv.image.shape[0]),.85)
                if len(matches)!=1:return None
                if progress['entry_pending']['cost']>settings['max_starlight']:return None
                box=inset_box(matches[0].box)
                progress['confirmation_pending']=dict(frame=frame,remaining=remaining,converted=converted)
                write_json(data/'star-selection-progress.json',progress)
                self.journal.record('star_confirmation_intent',**progress['confirmation_pending'],
                    choices=progress['selected'],cost=progress['entry_pending']['cost'],verified_clear=False)
            delay=random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
            if not confirming:self.journal.record('star_conversion_disable_intent',frame=frame,verified_clear=False)
        elif params.get('tutorial_back'):
            if argv.image.shape[1:] != (1920,3):
                return None
            detail=context.run_recognition_direct(JRecognitionType.TemplateMatch,
                JTemplateMatch(template=['navigation/tutorial-back.png'],roi=(75,25,135,95),
                               threshold=[.92]),argv.image)
            if detail is None or not detail.hit or len(detail.filtered_results)!=1:
                return None
            b=detail.filtered_results[0].box
            box=inset_box((b.x,b.y,b.w,b.h) if hasattr(b,'x') else tuple(b))
            delay=random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
        elif params.get('battle_mode')=='plan_once':
            if context.tasker.controller.info.get('type')=='adb':
                self.journal.record('battle_planning_blocked',frame=frame,
                    reason='Windows P key is not an Android keycode; verified touch control required',verified_clear=False)
                return None
            if self.battle_before is not None:return None
            self.battle_before=hashlib.sha256(argv.image.tobytes()).hexdigest()
            box,delay=(0,0,1,1),random.randint(180,480)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
            self.journal.record('battle_plan_requested',frame=frame,key=80,
                scope='Lix P selection through Maa ClickKey; no Enter or EGO input',verified_clear=False)
        elif params.get('deployment_mode'):
            if self.team is None:return None
            size=(argv.image.shape[1],argv.image.shape[0])
            state=observe_deployment(records,size)
            if self.deployment_pending:
                previous,target=self.deployment_pending
                if state is None or state.selected!=previous.selected+1 or state.capacity!=previous.capacity or state.order!=previous.order+(target,):
                    self.journal.record('deployment_transition_unconfirmed',frame=frame,
                        expected_sinner=target,expected_count=previous.selected+1,verified_clear=False)
                    return None
                self.deployment_pending=None
                self.journal.record('deployment_click_verified',frame=frame,sinner=target,
                    count=state.selected,order=state.order,scope='count and local OCR ordinal badges; not live identity proof')
            decision,sinner=next_sinner(state,self.team)
            if decision=='stop':
                self.journal.record('deployment_blocked',frame=frame,
                    reason='missing_or_mismatched_counter_badges_saved_order',verified_clear=False)
            mode=params['deployment_mode']
            if mode=='complete':
                if decision!='complete':return None
                box,delay=(0,0,1,1),0
            elif mode=='next':
                if decision!='select':return None
                self.deployment_pending=(state,sinner)
                box,delay=target_box(sinner,size),random.randint(180,480)
                context.override_pipeline({argv.node_name:{'pre_delay':delay}})
                self.journal.record('deployment_click_planned',frame=frame,sinner=sinner,
                    count=state.selected,capacity=state.capacity,target=box,verified_clear=False)
            else:raise ValueError('Unknown deployment mode')
        elif params.get('theme_mode'):
            catalog=self.theme_catalog()
            difficulty=theme_page(argv.image,catalog,records,self.locale)
            if params['theme_mode']=='enable_hard':
                if difficulty!='normal':return None
                size=(argv.image.shape[1],argv.image.shape[0])
                if not find(records,r'^SELECT\s*FLOOR\s*1\s*THEME\s*PACK$',(.38,.13,.63,.20),size,.85):return None
                matches=catalog.matches(argv.image,'normal_mode',(.61,0,.83,.13))
                if len(matches)!=1:return None
                path=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))/'difficulty-switch-progress.json'
                progress=read_json(path) if path.exists() else {}
                if progress.get('pending'):raise ValueError('Difficulty switch result unverified; do not repeat')
                progress['pending']=dict(before='normal',requested='hard',frame=str(self.journal.directory/(frame+'.png')))
                write_json(path,progress)
                self.journal.record('difficulty_switch_intent',**progress['pending'],verified_clear=False)
                x,y,w,h=matches[0];scale=argv.image.shape[1]/1920
                box=(x+round(110*scale),y+round(13*scale),round(40*scale),round(24*scale))
                delay=random.randint(350,750)
                context.override_pipeline({argv.node_name:{'pre_delay':delay}})
            elif params['theme_mode']=='normal':
                if difficulty!='normal':return None
                box,delay=(0,0,1,1),0
            elif params['theme_mode']=='recommend':
                if difficulty!='hard' or self.team is None:return None
                candidates=pack_candidates(argv.image,records,catalog)
                target,ranking=recommend_pack(candidates,self.team)
                self.journal.record('theme_pack_ranking',frame=frame,team_slot=self.team.slot,
                    difficulty=difficulty,ranking=ranking,candidates=[dict(name=c.name,box=c.box,new=c.new) for c in candidates],
                    selected=False,refreshed=False,verified_clear=False)
                if target is None:return None
                x,y,w,h=target['box'];scale=argv.image.shape[1]/1280
                # Start inside the card away from the magnifier; never click details.
                begin=[x+round(.42*w),y+round(75*scale),max(1,round(.16*w)),max(1,round(12*scale))]
                end=[begin[0],begin[1]+round(400*scale),begin[2],begin[3]]
                if end[1]+end[3]>argv.image.shape[0]:return None
                context.override_pipeline({argv.node_name:dict(begin=begin,end=end,duration=random.randint(480,680))})
                box,delay=tuple(begin),random.randint(180,480)
                context.override_pipeline({argv.node_name:{'pre_delay':delay}})
            else:raise ValueError('Unknown theme recognition mode')
        elif params.get('gift_mode') == 'recommend':
            if scene != 'FLOOR_GIFTS' or self.team is None:
                return None
            if self.gifts is None:
                self.gifts = GiftCatalog(ROOT/'assets/resource/base')
            candidates = floor_candidates(argv.image,records,self.locale,self.gifts)
            target,ranking = recommend(candidates,self.team)
            self.journal.record('floor_gift_ranking',frame=frame,team_slot=self.team.slot,
                ranking=ranking,candidates=[{'name':c.gift.name,'owned':c.gift.owned,
                    'box':c.box,'evidence':c.evidence} for c in candidates],
                selected=False,reward_received=False)
            if target is None:
                return None
            box,delay = target.box,random.randint(180,480)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
        elif mode:
            if self.team is None:
                return None
            size = (argv.image.shape[1], argv.image.shape[0])
            row = team_row(records, self.team, self.locale_name, size)
            header = team_header(records, self.team, self.locale_name, size)
            if mode == 'verified':
                if header is None or row is None:
                    return None
                box = inset_box(header.box)
            elif mode == 'confirm':
                if scene!='DUNGEON_TEAM' or header is None or row is None:
                    return None
                matches=find(records,self.locale['gift_confirm'],(.82,.76,.96,.88),size,.85)
                if len(matches)!=1:return None
                box=inset_box(matches[0].box)
            elif mode == 'level_warning':
                if scene!='LEVEL_WARNING' or header is None or row is None:return None
                matches=find(records,self.locale['gift_confirm'],(.53,.64,.68,.72),size,.85)
                if len(matches)!=1:return None
                box=inset_box(matches[0].box)
            elif mode == 'row':
                if row is None or header is not None:
                    return None
                box = inset_box(row.box)
            elif mode == 'scroll':
                if row is not None or self.scroll_count >= 8:
                    return None
                # Stop a stuck/bottom-of-list scrollbar after one unchanged page.
                digest = hashlib.sha256(json.dumps([(r.text,r.box) for r in records
                    if r.box[0] < .19*size[0]], sort_keys=True).encode()).hexdigest()
                if digest == self.scroll_hash:
                    return None
                self.scroll_hash = digest
                self.scroll_count += 1
                w,h = size
                start = [round(.10*w), round(.70*h), 4, 4]
                end = [round(.10*w), round(.34*h), 4, 4]
                context.override_pipeline({argv.node_name: {'begin': start, 'end': end,
                                                            'duration': random.randint(420,620)}})
                box = tuple(start)
            else:
                raise ValueError('Unknown saved-team recognition mode')
            delay = random.randint(180,480)
            context.override_pipeline({argv.node_name: {'pre_delay': delay}})
        elif params.get('battle_mode')=='start_turn':
            # Submit the assigned turn: the battle's own `START` action. No skill or
            # target is chosen here; the page must already be an assigned battle.
            if scene!='BATTLE_HUD':return None
            size=(argv.image.shape[1],argv.image.shape[0])
            plan=begin_turn_plan(records,size,argv.image)
            if plan['target'] is None:
                self.journal.record('battle_turn_blocked',frame=frame,scene=scene,
                                    reason=plan['reason'],verified_clear=False)
                return None
            box=inset_box(plan['target'],.2)
            delay=random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
            self.journal.record('battle_turn_intent',frame=frame,scene=scene,
                                wave=plan['wave'],turn=plan['turn'],box=box,
                                delay_ms=delay,victory_verified=False,verified_clear=False)
        elif params.get('battle_mode')=='win_rate':
            # Android touch equivalent of the upstream win-rate step: one bounded
            # tap on the battle's own Win Rate button. Skill slots, targets and the
            # turn are not touched here.
            if scene!='BATTLE_HUD':return None
            size=(argv.image.shape[1],argv.image.shape[0])
            plan=auto_assign_plan(records,size)
            if plan['target'] is None:
                self.journal.record('battle_auto_assign_blocked',frame=frame,scene=scene,
                                    reason=plan['reason'],verified_clear=False)
                return None
            box=inset_box(plan['target'],.2)
            delay=random.randint(350,750)
            context.override_pipeline({argv.node_name:{'pre_delay':delay}})
            self.journal.record('battle_auto_assign_intent',frame=frame,scene=scene,
                                wave=plan['wave'],turn=plan['turn'],box=box,
                                damage_box=plan['damage'],delay_ms=delay,
                                turn_submitted=False,verified_clear=False)
        elif 'token' in params:
            matches = find(records, self.locale[params['token']], params['roi'],
                           (argv.image.shape[1], argv.image.shape[0]))
            if len(matches) != 1:
                return None
            box = inset_box(matches[0].box)
            # Maa performs the click; random delay is an explicit bounded node override.
            delay = random.randint(180, 480)
            context.override_pipeline({argv.node_name: {'pre_delay': delay}})
        else:
            box, delay = (0, 0, 1, 1), 0
        if delay and self.input_validator is not None:
            self.input_validator()
        result = {'scene': scene, 'frame': frame, 'target': box, 'pre_delay_ms': delay}
        self.journal.record('recognized', node=argv.node_name, **result)
        return CustomRecognition.AnalyzeResult(box, result)

    def read_number(self,context,image,roi):
        detail=context.run_recognition_direct(JRecognitionType.OCR,
            JOCR(roi=roi,only_rec=True,expected=[r'^\s*\d{1,4}\s*$'],threshold=.85),image)
        if detail is None or not detail.hit:return None
        results=[r for r in detail.filtered_results if hasattr(r,'text')]
        if len(results)!=1:return None
        return int(results[0].text.strip())


class DifficultyProof(CustomAction):
    def __init__(self,recognition):
        super().__init__();self.recognition=recognition

    @guarded_callback(False)
    def run(self,context,argv):
        path=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))/'difficulty-switch-progress.json'
        progress=read_json(path)
        if not progress.get('pending'):return False
        wait_job(context.tasker.controller.post_screencap(),timeout=5)
        image=context.tasker.controller.cached_image
        records,scene,frame=self.recognition.observe(context,image)
        difficulty=theme_page(image,self.recognition.theme_catalog(),records,self.recognition.locale)
        verified=scene=='THEME_PACKS' and difficulty=='hard'
        self.recognition.journal.record('difficulty_switch_observation',frame=frame,
            difficulty=difficulty,verified=verified,verified_clear=False)
        if not verified:return False
        progress['pending']=None;progress['confirmed']='hard'
        progress['proof']=str(self.recognition.journal.directory/(frame+'.png'))
        write_json(path,progress)
        return True


class InitialReceiptProof(CustomAction):
    def __init__(self,recognition):
        super().__init__();self.recognition=recognition

    @guarded_callback(False)
    def run(self,context,argv):
        path=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))/'initial-gift-progress.json'
        progress=read_json(path);pending=progress.get('receipt_pending')
        if not pending:return False
        titles=initial_gifts.proven_titles(progress,ROOT/'evidence/runtime')
        index=len(progress.get('acknowledged',[]))
        wait_job(context.tasker.controller.post_screencap(),timeout=5)
        image=context.tasker.controller.cached_image
        records,scene,frame=self.recognition.observe(context,image)
        name=initial_gifts.receipt_name(records,(image.shape[1],image.shape[0]))
        verified=(index+1<len(titles) and scene=='GIFT_GET'
                  and initial_gifts.same_name(name,titles[index+1]))
        owned=[]
        if index+1==len(titles) and scene=='GIFT_SEARCH':
            catalog=self.recognition.gift_catalog()
            owned=search_owned_names(image,records,catalog)
            expected=[catalog.text_identity(t) for t in titles]
            verified=(None not in expected and len(set(expected))==len(titles)
                      and set(expected)<={g['name'] for g in owned})
        self.recognition.journal.record('initial_receipt_ack_observation',frame=frame,title=name,
            previous=pending['title'],owned=owned,verified=verified,verified_clear=False)
        if not verified:return False
        progress.setdefault('acknowledged',[]).append(pending['choice'])
        progress.setdefault('receipt_evidence',[]).append(dict(before=pending['frame'],
            after=str(self.recognition.journal.directory/(frame+'.png')),title=pending['title']))
        progress['receipt_pending']=None
        write_json(path,progress)
        return True


class InitialGiftProof(CustomAction):
    def __init__(self,recognition):
        super().__init__();self.recognition=recognition

    @guarded_callback(False)
    def run(self,context,argv):
        data=Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))
        path=data/'initial-gift-progress.json';progress=read_json(path)
        pending=progress.get('pending')
        if pending is None:return False
        wait_job(context.tasker.controller.post_screencap(),timeout=5)
        image=context.tasker.controller.cached_image
        records,scene,frame=self.recognition.observe(context,image)
        size=(image.shape[1],image.shape[0])
        count=initial_gifts.counter(records,size)
        rows=initial_gifts.selected_rows(image)
        target=initial_gifts.row_target(records,size,pending['choice'])
        expected=sorted(progress['selected']+[pending['choice']])
        verified=(scene=='INITIAL_GIFTS' and count==(pending['count_before']+1,pending['capacity'])
                  and rows==expected and target is not None and target[1]==pending['title'])
        self.recognition.journal.record('initial_gift_selection_observation',frame=frame,count=count,
            rows=rows,title=target[1] if target else None,verified=verified,verified_clear=False)
        if not verified:return False
        progress['selected'].append(pending['choice']);progress['pending']=None
        progress['proof']=str(self.recognition.journal.directory/(frame+'.png'))
        write_json(path,progress)
        return True


class StarProof(CustomAction):
    def __init__(self,recognition):
        super().__init__();self.recognition=recognition

    @guarded_callback(False)
    def run(self,context,argv):
        if self.recognition.star_pending is None:return False
        path,pending=self.recognition.star_pending
        wait_job(context.tasker.controller.post_screencap(),timeout=5)
        image=context.tasker.controller.cached_image
        records,scene,frame=self.recognition.observe(context,image)
        available=self.recognition.read_number(context,image,(1515,45,54,40))
        verified=scene=='STAR_GRACES' and available==pending['available_before']-pending['cost']
        self.recognition.journal.record('star_selection_observation',choice=pending['choice'],
            frame=frame,available=available,verified=verified,enhance=False,verified_clear=False)
        if not verified:return False
        progress=read_json(path)
        if progress['pending']!=pending:return False
        progress['selected'].append(pending['choice'])
        progress['available_after']=available
        progress['pending']=None
        write_json(path,progress)
        self.recognition.star_pending=None
        return True


class TeamAction(CustomAction):
    """Configuration/evidence only. Native Pipeline owns every click/swipe."""
    def __init__(self, recognition):
        super().__init__()
        self.recognition = recognition

    def build(self, params, mode):
        """Set, extend, or file a saved team's keyword build.

        The team-build entry runs without a preceding loadout page, so the slot
        comes from the node parameter when no team has been selected yet; every
        mode writes the same profile file as the other preferences. The extra
        keywords arrive as free text from a ProjectInterface input, so an unknown
        name is journalled and skipped instead of raised: a typo must not latch
        the callback closed.
        """
        store=ProfileStore(Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))/'user-team-profiles.json')
        teams=list(store.load()) if store.path.exists() else []
        team=self.recognition.team
        if team is None:
            slot=int(params.get('slot',1))
            team=next((t for t in teams if t.slot==slot),Team(slot,frozenset()))
        index=next((i for i,t in enumerate(teams) if t.slot==team.slot),None)
        if mode=='save':
            configured=replace(team,name=str(params.get('name') or team.name))
        else:
            wanted=[str(k) for k in params.get('keywords') or [] if str(k)]
            known=[k for k in wanted if k in KEYWORDS]
            if len(known)!=len(wanted):
                self.recognition.journal.record('team_keywords_rejected',slot=team.slot,
                                                rejected=sorted(set(wanted)-set(known)))
            keywords=set(known) if mode=='keywords' else set(team.keywords)|set(known)
            configured=replace(team,keywords=frozenset(keywords))
        if index is None:teams.append(configured)
        else:teams[index]=configured
        store.save(teams)
        self.recognition.team=configured
        self.recognition.journal.record('team_build_saved' if mode=='save' else 'team_preferences_saved',
            slot=configured.slot,name=configured.name,keywords=sorted(configured.keywords),field=mode)
        return True

    @guarded_callback(False)
    def run(self, context, argv):
        params = json.loads(argv.custom_action_param or '{}')
        mode=params.get('mode')
        if mode in ('keywords','keywords_add','save'):
            return self.build(params,mode)
        if mode in ('name','pack','weight','deployment','deployment_slot','deployment_commit'):
            team=self.recognition.team
            if team is None:return False
            if mode=='pack':
                pack=params.get('name','')
                if pack and pack not in self.recognition.theme_catalog().names:
                    raise ValueError('Unknown theme preference')
                self.recognition.pending_pack=pack
                return True
            if mode=='name':configured=replace(team,name=str(params.get('name',team.name)))
            elif mode in ('deployment_slot','deployment_commit'):
                if self.recognition.deployment_draft is None:return True
                if mode=='deployment_slot':
                    self.recognition.deployment_draft.choose(params.get('position'),params.get('sinner'))
                    return True
                configured=replace(team,deployment=self.recognition.deployment_draft.finish())
            elif mode=='deployment':
                preset=params.get('preset','saved')
                self.recognition.deployment_draft=None
                if preset=='custom':
                    self.recognition.deployment_draft=DeploymentDraft()
                    return True
                if preset=='saved':
                    if not team.deployment:
                        self.recognition.journal.record('deployment_blocked',reason='saved_order_not_configured',verified_clear=False)
                    return bool(team.deployment)
                if preset!='natural':raise ValueError('Unknown deployment preset')
                configured=replace(team,deployment=SINNERS)
            else:
                if not self.recognition.pending_pack:return True
                weights=dict(team.pack_weights);weights[self.recognition.pending_pack]=params['weight']
                configured=replace(team,pack_weights=tuple(weights.items()))
            store=ProfileStore(Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))/'user-team-profiles.json')
            teams=list(store.load())
            index=next(i for i,t in enumerate(teams) if t.slot==team.slot)
            teams[index]=configured;store.save(teams)
            self.recognition.team=configured
            if mode=='deployment_commit':self.recognition.deployment_draft=None
            self.recognition.journal.record('team_preferences_saved',slot=team.slot,field=mode)
            return True
        if params.get('mode') == 'configure':
            slot = int(params.get('slot',1))
            store=ProfileStore(Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))/'user-team-profiles.json')
            teams=list(store.load()) if store.path.exists() else []
            existing=next((t for t in teams if t.slot==slot),Team(slot,frozenset()))
            configured=replace(existing,name=str(params.get('name',existing.name)))
            index=next((i for i,t in enumerate(teams) if t.slot==slot),None)
            if index is None: teams.append(configured)
            else: teams[index]=configured
            store.save(teams)
            self.recognition.team = configured
            self.recognition.scroll_count, self.recognition.scroll_hash = 0, None
            self.recognition.pending_pack=''
            self.recognition.deployment_pending=None
            self.recognition.deployment_draft=None
            self.recognition.journal.record('team_target', slot=slot, name=self.recognition.team.name)
            return True
        if mode!='verified':
            raise ValueError('Unknown saved-team action mode')
        # Take a new observation after selection, rather than trusting an old OCR box.
        try:
            wait_job(context.tasker.controller.post_screencap(),timeout=5)
        except (TimeoutError,RuntimeError):
            return False
        image = context.tasker.controller.cached_image
        records, scene, frame = self.recognition.observe(context,image)
        team = self.recognition.team
        if (scene != params.get('scene','TEAM_LIBRARY') or team is None
            or team_header(records,team,self.recognition.locale_name,(image.shape[1],image.shape[0])) is None
            or team_row(records,team,self.recognition.locale_name,(image.shape[1],image.shape[0])) is None):
            return False
        self.recognition.journal.record('team_selected', slot=team.slot, name=team.name,
            frame=frame, scene=scene, scope='Saved team header and row verified; no battle deployment or clear assertion')
        return True


class ThemeObservation(CustomAction):
    """Retain a fresh post-drag frame; no speculative map/selection success."""
    def __init__(self,recognition):
        super().__init__();self.recognition=recognition

    @guarded_callback(False)
    def run(self,context,argv):
        try:
            wait_job(context.tasker.controller.post_screencap(),timeout=5)
        except (TimeoutError,RuntimeError):return False
        image=context.tasker.controller.cached_image
        records,scene,frame=self.recognition.observe(context,image)
        size=(image.shape[1],image.shape[0])
        header=map_header(records,size) if scene=='MAP' else None
        # The pack line must equal the pack this run planned; any other name keeps
        # the selection unproven instead of borrowing an unrelated page as proof.
        status='not_applicable'
        if header is not None:
            status=('verified' if header.pack==self.recognition.pending_pack
                    else 'header_pack_differs_from_pending')
        self.recognition.journal.record('theme_map_postcondition',frame=frame,scene=scene,
            floor=None if header is None else header.floor,
            pack=None if header is None else header.pack,
            pending_pack=self.recognition.pending_pack,status=status,
            selected=status=='verified',verified_clear=False,
            reason=('pack_drag_selection_substantiated_by_fresh_floor_header'
                    if status=='verified' else
                    ('fresh_map_header_names_a_different_pack' if header is not None else
                     'fresh_post_drag_frame_is_not_an_identified_map_page')))
        if header is not None:
            self.recognition.journal.record('map_observed',frame=frame,floor=header.floor,
                pack=header.pack,route=route_decision(header,size),
                scope='header identity and bounded route refusal; no node identity or input')
        return True


class DeploymentProof(CustomAction):
    def __init__(self,recognition):
        super().__init__();self.recognition=recognition

    @guarded_callback(False)
    def run(self,context,argv):
        try:wait_job(context.tasker.controller.post_screencap(),timeout=5)
        except (TimeoutError,RuntimeError):return False
        image=context.tasker.controller.cached_image
        records,scene,frame=self.recognition.observe(context,image)
        team=self.recognition.team
        state=observe_deployment(records,(image.shape[1],image.shape[0]))
        if scene!='DEPLOYMENT' or team is None or self.recognition.deployment_pending or next_sinner(state,team)[0]!='complete':return False
        self.recognition.journal.record('deployment_order_observed',frame=frame,team_slot=team.slot,
            order=state.order,count=state.selected,capacity=state.capacity,
            battle_started=False,verified_clear=False,scope='local OCR order badges and count; experimental grid geometry, no live proof')
        return True


class BattlePlanObservation(CustomAction):
    def __init__(self,recognition):
        super().__init__();self.recognition=recognition

    @guarded_callback(False)
    def run(self,context,argv):
        try:wait_job(context.tasker.controller.post_screencap(),timeout=5)
        except (TimeoutError,RuntimeError):return False
        image=context.tasker.controller.cached_image
        records,scene,frame=self.recognition.observe(context,image)
        changed=hashlib.sha256(image.tobytes()).hexdigest()!=self.recognition.battle_before
        self.recognition.journal.record('battle_plan_observed',frame=frame,scene=scene,
            frame_changed=changed,labels=preview_labels(records,(image.shape[1],image.shape[0])),
            plan_verified=False,clash_coverage_verified=False,turn_submitted=False,
            victory_verified=False,verified_clear=False,
            reason='fresh_frame_only_clash_assignment_EGO_survival_and_turn_submission_pending')
        return True


class MapObservation(CustomAction):
    """Read-only map identity check: records the page and sends no input."""
    def __init__(self,recognition):
        super().__init__();self.recognition=recognition

    @guarded_callback(False)
    def run(self,context,argv):
        try:
            wait_job(context.tasker.controller.post_screencap(),timeout=5)
        except (TimeoutError,RuntimeError):return False
        image=context.tasker.controller.cached_image
        records,scene,frame=self.recognition.observe(context,image)
        size=(image.shape[1],image.shape[0])
        header=map_header(records,size) if scene=='MAP' else None
        panel=node_panel(records,size) if scene=='NODE_PANEL' else None
        team=pre_battle_team_page(records,size) if scene=='PRE_BATTLE_TEAM' else None
        self.recognition.journal.record('map_observed',frame=frame,scene=scene,
            floor=None if header is None else header.floor,
            pack=None if header is None else header.pack,
            header_box=None if header is None else header.exploring_text.box,
            pack_box=None if header is None else header.pack_text.box,
            panel_title=None if panel is None else panel.title,
            panel_enter_box=None if panel is None else panel.enter.box,
            panel_clear_rewards=None if panel is None or panel.clear_rewards is None
            else panel.clear_rewards.box,
            panel_cost_texts=None if panel is None else list(panel.cost_texts),
            battle_box=None if team is None else team.battle.box,
            clear_selection_box=None if team is None else team.clear_selection.box,
            participant_texts=None if team is None else list(team.participants),
            route=route_decision(header,size),
            input_sent=False,verified_clear=False,
            scope='fresh page identity and bounded route refusal; no node input')
        return header is not None or panel is not None or team is not None


class BattleObservation(CustomAction):
    """Read-only battle page recorder: identity, controls and frame change only."""
    def __init__(self,recognition):
        super().__init__();self.recognition=recognition

    @guarded_callback(False)
    def run(self,context,argv):
        try:
            wait_job(context.tasker.controller.post_screencap(),timeout=5)
        except (TimeoutError,RuntimeError):return False
        image=context.tasker.controller.cached_image
        records,scene,frame=self.recognition.observe(context,image)
        size=(image.shape[1],image.shape[0])
        digest=hashlib.sha256(image.tobytes()).hexdigest()
        changed=digest!=self.recognition.battle_before
        self.recognition.battle_before=digest
        hud=battle_hud(records,size)
        buttons=auto_assign_buttons(records,size)
        begin=start_button(records,size,image)
        self.recognition.journal.record('battle_observed',frame=frame,scene=scene,
            frame_changed=changed,wave=None if hud is None else hud['wave'],
            turn=None if hud is None else hud['turn'],
            diagnostics=[] if hud is None else hud['diagnostics'],
            auto_assign_buttons=None if buttons is None else
                {'win_rate':list(buttons['win_rate']),'damage':list(buttons['damage'])},
            start_box=None if begin is None else list(begin),
            turn_submitted=False,verified_clear=False,
            scope='page identity, HUD counters and battle controls; no input')
        return hud is not None


class InputPreflight(CustomAction):
    def __init__(self,recognition):
        super().__init__(); self.recognition=recognition

    @guarded_callback(False)
    def run(self,context,argv):
        try:
            lease=ControllerLease.acquire(ROOT/'build/controller.lock')
        except OSError:
            self.recognition.journal.record('preflight_failed',reason='another_controller_owns_game')
            return False
        info=context.tasker.controller.info
        if info.get('type')=='adb':
            try:
                self.recognition.input_validator=lambda:controller_foreground(context.tasker.controller.info)
                identity=self.recognition.input_validator()
            except Exception as error:
                self.recognition.journal.record('preflight_failed',reason=str(error))
                lease.close();return False
            self.recognition.journal.record('preflight_passed',controller='adb',foreground=identity,
                address=info['adb_serial'])
            return True
        if info.get('type')!='win32':
            self.recognition.journal.record('preflight_failed',reason='unsupported_actual_controller_binding')
            lease.close();return False
        windows=[w for w in Toolkit.find_desktop_windows()
                 if w.window_name=='LimbusCompany' and w.class_name=='UnityWndClass']
        if len(windows)!=1:
            self.recognition.journal.record('preflight_failed',reason='game_window_not_unique')
            lease.close()
            return False
        try:
            identity=check_window(windows[0].hwnd)
        except InputPermissionError as error:
            self.recognition.journal.record('preflight_failed',reason='windows_integrity_mismatch',**error.identity)
            lease.close()
            return False
        self.recognition.input_validator=lambda:check_window(windows[0].hwnd)
        self.recognition.journal.record('preflight_passed',**identity)
        return True


class LimbusTerminal(CustomAction):
    def __init__(self, recognition):
        super().__init__()
        self.recognition = recognition

    @guarded_callback(False)
    def run(self, context, argv):
        params = json.loads(argv.custom_action_param or '{}')
        self.recognition.journal.record('terminal', reason=params['reason'],
                                       last_scene=self.recognition.last_scene,
                                       verified_clear=False)
        return False


# ------------------------------------------------------------------ the whole run


#: The environment variable that aims one run's evidence at a known directory.
LOOP_DIR_ENV = 'MAALIMBUS_RUN_DIR'
#: Every runner setting can also be overridden as ``MAALIMBUS_LOOP_<SETTING>``.
LOOP_ENV_PREFIX = 'MAALIMBUS_LOOP_'
#: A whole run's own wall clock. A node's ``timeout`` is the timeout of its ``next``
#: list, not of a custom action, so the run has to bound itself.
LOOP_BUDGET_SECONDS = 5400.0
#: This action's defaults on top of the runner's: the CLI defaults describe one
#: one-shot window, while this node drives the whole dungeon and its run ledger.
LOOP_DEFAULTS = {'steps': 400, 'run_store': 'config/user-run-ledger.json'}
#: Node parameters that are not runner settings.
LOOP_EXTRA_PARAMS = ('directory', 'budget')


def loop_flag(raw):
    """An environment string as the boolean it means."""
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def loop_environment():
    """Read every ``MAALIMBUS_LOOP_<SETTING>`` override, typed like its default.

    The CLI cannot pass a node's ``custom_action_param``, so the environment is how a
    live run is aimed without a second controller or an edit to the pipeline.
    """
    chosen = {}
    for name, default in runner.settings().as_dict().items():
        raw = os.environ.get(LOOP_ENV_PREFIX + name.upper())
        if raw is None:
            continue
        if isinstance(default, bool):
            chosen[name] = loop_flag(raw)
        elif isinstance(default, int):
            chosen[name] = int(raw)
        elif isinstance(default, float):
            chosen[name] = float(raw)
        else:
            chosen[name] = raw or None
    return chosen


def loop_parameters(params):
    """One run's settings, and the parameters that were not settings.

    Precedence: the CLI defaults, this action's whole-run defaults, the environment,
    then the node's own ``custom_action_param``. A parameter the runner does not know
    is reported rather than silently kept, so a typo shows up in the run journal.
    """
    known = set(runner.settings().as_dict())
    chosen = dict(LOOP_DEFAULTS)
    launch_path = Path(os.environ.get('MAALIMBUS_DATA_PATH', ROOT/'config'))/'user-launch.json'
    if launch_path.exists():
        saved_launch = read_json(launch_path)
        chosen.update({key: saved_launch[key] for key in
                       ('graces','grace_budget','gift_keyword','gift_search') if key in saved_launch})
    chosen.update(loop_environment())
    chosen.update({key: value for key, value in params.items() if key in known})
    ignored = sorted(set(params) - known - set(LOOP_EXTRA_PARAMS))
    return runner.settings(chosen), ignored


def loop_budget(params):
    """How long the run may take, in seconds."""
    raw = params.get('budget')
    if raw is None:
        raw = os.environ.get(LOOP_ENV_PREFIX + 'BUDGET')
    return LOOP_BUDGET_SECONDS if raw is None else max(1.0, float(raw))


def loop_directory(params):
    """Where one run's evidence goes: the node, the environment, then a fresh stamp."""
    chosen = params.get('directory') or os.environ.get(LOOP_DIR_ENV)
    if chosen:
        directory = Path(chosen)
        if not directory.is_absolute():
            directory = ROOT / directory
    else:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        directory = ROOT / 'evidence/runtime' / ('pi-' + stamp)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def loop_store(settings, journal):
    """The run ledger the CLI uses, or ``(None, None)`` when it cannot be opened.

    ``RunStore`` refuses a ledger written for another rotation and a team list that
    repeats. A run is still worth driving when only its bookkeeping is unavailable, so
    the refusal is journalled and the loop goes on without a ledger. An opened ledger
    also decides the team, because the rotation is what says which team enters next.
    """
    path = settings.run_store
    if not path or settings.observe_only:
        return None, None
    ledger = Path(str(path))
    if not ledger.is_absolute():
        ledger = ROOT / ledger
    try:
        existing = read_json(ledger) if ledger.exists() else None
        slots = existing['team_slots'] if existing else [settings.team]
        store = RunStore(ledger, [SimpleNamespace(slot=slot) for slot in slots])
        run_id = store.start()
    except (OSError, ValueError, KeyError, TypeError) as error:
        journal.record('mirror_loop_store_skipped', path=str(path), error=str(error))
        return None, None
    settings.team = store.team_slot
    return store, run_id


def write_loop_result(directory, result):
    """Write one run's summary next to its evidence and return the path."""
    path = Path(directory) / 'agent-result.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str),
                    encoding='utf-8')
    return path


class AgentJob:
    """The job surface ``run_node`` reads, for a node already run to its end.

    ``Context.run_task`` is synchronous, so the job standing for it is never pending:
    a caller that polls ``done`` sees it finished without waiting for anything.
    """

    def __init__(self, detail):
        self.detail = detail
        self.done = True
        self.succeeded = bool(detail is not None and detail.status.succeeded)


class AgentTasker:
    """A tasker that runs pipeline nodes through ``Context.run_task``.

    ``context.tasker.post_task`` cannot be used from inside a custom action: the
    framework's task runner is a single worker, so a node posted here queues behind the
    very task that is waiting for it, and the wait ends in a stop that kills this run.
    ``Context.run_task`` is the framework's own way to run a node from a callback -- it
    runs the sub-task synchronously on this thread.

    ``MaaObserver`` reads ``context.tasker`` and calls ``post_task`` on what it finds,
    so this proxy is both the context the observer is handed and the tasker it drives.
    """

    def __init__(self, context):
        self.context = context
        self.tasker = self
        self.entries = []

    def post_task(self, entry, pipeline_override=None):
        self.entries.append(entry)
        return AgentJob(self.context.run_task(entry, pipeline_override))

    def post_stop(self):
        """Nothing to stop: every node this proxy posts has already finished."""
        return AgentJob(None)


class MirrorLoopAction(CustomAction):
    """Drive a whole Mirror Dungeon run from inside the task the agent already owns.

    The loop is :mod:`maalimbus.runner` -- the same one ``tools/window_step.py`` drives
    from the command line -- and this action only supplies the Maa instances the PI
    gave the agent: the controller as the device, ``context.run_task`` as the tasker the
    observation nodes run through, and the run directory as the evidence journal. Input
    leaves through the controller's own ``post_click``/``post_swipe``, because that
    controller is the process that owns the device.

    The run always reports through the journal: ``mirror_loop_start`` once,
    ``mirror_loop_stopped`` when the loop returns, whatever its reason, and
    ``mirror_loop_error`` with a traceback when the wiring or the device failed. The
    summary the runner returns is written to ``agent-result.json`` in the run directory.
    """

    def __init__(self, recognition):
        super().__init__()
        self.recognition = recognition

    @guarded_callback(False)
    def run(self, context, argv):
        params = json.loads(argv.custom_action_param or '{}')
        directory = loop_directory(params)
        settings, ignored = loop_parameters(params)
        budget = loop_budget(params)
        deadline = time.monotonic() + budget
        # The observation nodes journal through the recognition and the loop reads the
        # run directory, so both halves of one run share one journal.
        journal = Journal(directory)
        self.recognition.journal = journal
        result = dict(pid=os.getpid(), address=settings.address, controller='Maa AgentServer',
                      observe_only=bool(settings.observe_only), steps=[], clicks_sent=0,
                      verified_clear=False, foreground_before=None)
        loop = None
        try:
            device = runner.MaaDevice(context.tasker.controller, deadline=deadline)
            observer = runner.MaaObserver(AgentTasker(context), directory)
            store, run_id = loop_store(settings, journal)
            if store is not None:
                result['run_ledger'] = dict(path=str(store.path), run=run_id,
                                            team=store.team_slot,
                                            rotation=store.data['rotation'])
            journal.record('mirror_loop_start', directory=str(directory), budget=budget,
                           deadline=deadline, ignored_params=ignored, **settings.as_dict())
            loop = runner.MirrorRunner(device, settings=settings,
                locale=self.recognition.locale_name,
                registry=json.loads(runner.REGISTRY.read_text(encoding='utf-8')),
                store=store, directory=directory, journal=journal, observer=observer,
                run_id=run_id, result=result)
            loop.configure(deadline=deadline)
            result = loop.run(steps=1 if settings.observe_only else int(settings.steps),
                              interval=float(settings.interval),
                              round_limit=1 if settings.observe_only else int(settings.steps),
                              deadline=deadline)
        except TimeoutError as error:
            # This run's own budget, or a device job that outlived its own timeout: a
            # bounded stop, reported with the record of what already happened.
            result = loop.summary() if loop is not None else result
            result['reason'] = 'loop_deadline_exceeded'
            result['error'] = str(error)
        except Exception as error:
            journal.record('mirror_loop_error', error=str(error),
                           error_type=type(error).__name__, traceback=traceback.format_exc(),
                           verified_clear=False)
            write_loop_result(directory, {'reason': 'mirror_loop_failed', 'error': str(error),
                                          'error_type': type(error).__name__})
            return False
        write_loop_result(directory, result)
        journal.record('mirror_loop_stopped', reason=result.get('reason'),
                       steps=len(result.get('steps') or []),
                       clicks_sent=result.get('clicks_sent', 0),
                       passed=result.get('passed'), directory=str(directory))
        return True
