import hashlib
import json
import os
import random
from dataclasses import replace
from functools import wraps
from pathlib import Path

import cv2
from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from maa.pipeline import JOCR, JRecognitionType
from maa.toolkit import Toolkit

from maalimbus.vision import Text, classify, find, inset_box
from maalimbus.policies import Team
from maalimbus.team_vision import team_row, team_header
from maalimbus.windows_preflight import check_window, InputPermissionError
from maalimbus.storage import ProfileStore
from maalimbus.controller_lease import ControllerLease
from maalimbus.gift_vision import GiftCatalog, floor_candidates, recommend
from maalimbus.jobs import wait_job
from maalimbus.runtime_paths import ROOT
from maalimbus.theme_vision import ThemeCatalog, theme_page, pack_candidates, recommend_pack
from maalimbus.deployment import deployment_page,observe_deployment,next_sinner,target_box,badge_rois,DeploymentDraft
from maalimbus.storage import SINNERS
from maalimbus.battle_vision import BattleCatalog,planning_anchors,preview_labels


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
        data = {'event': event, **details}
        with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as file:
            file.write(json.dumps(data, ensure_ascii=False) + '\n')

    def frame(self, frame, records, scene, **extra):
        self.index += 1
        name = f'frame-{self.index:04d}'
        cv2.imwrite(str(self.directory / (name + '.png')), frame)
        data = {'scene': scene, 'size': [frame.shape[1], frame.shape[0]],
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

    def theme_catalog(self):
        if self.themes is None:
            self.themes=ThemeCatalog(ROOT/'assets/resource/base')
        return self.themes

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
        scene = classify(records, self.locale, (image.shape[1], image.shape[0]))
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
        if scene=='UNKNOWN' and theme_page(image,self.theme_catalog()):
            scene='THEME_PACKS'
        if scene=='UNKNOWN' and planning_anchors(image,self.battle_catalog(),self.locale_name):
            scene='BATTLE_PLANNING'
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
        if params.get('battle_mode')=='plan_once':
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
            difficulty=theme_page(argv.image,catalog)
            if params['theme_mode']=='normal':
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
        result = {'scene': scene, 'frame': frame, 'target': box, 'pre_delay_ms': delay}
        self.journal.record('recognized', node=argv.node_name, **result)
        return CustomRecognition.AnalyzeResult(box, result)


class TeamAction(CustomAction):
    """Configuration/evidence only. Native Pipeline owns every click/swipe."""
    def __init__(self, recognition):
        super().__init__()
        self.recognition = recognition

    @guarded_callback(False)
    def run(self, context, argv):
        params = json.loads(argv.custom_action_param or '{}')
        mode=params.get('mode')
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
        if (scene != 'TEAM_LIBRARY' or team is None
            or team_header(records,team,self.recognition.locale_name,(image.shape[1],image.shape[0])) is None
            or team_row(records,team,self.recognition.locale_name,(image.shape[1],image.shape[0])) is None):
            return False
        self.recognition.journal.record('team_selected', slot=team.slot, name=team.name,
            frame=frame, scope='Sinners saved-team library; no dungeon entry or deployment assertion')
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
        records,scene,frame=self.recognition.observe(context,context.tasker.controller.cached_image)
        self.recognition.journal.record('theme_drag_observation',frame=frame,scene=scene,
            selected=False,verified_clear=False,
            reason='fresh_observation_only_map_postcondition_not_implemented')
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
