import hashlib
import json
import os
import random
from dataclasses import replace
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


class Journal:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.index = 0

    def record(self, event, **details):
        data = {'event': event, **details}
        with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as file:
            file.write(json.dumps(data, ensure_ascii=False) + '\n')

    def frame(self, frame, records, scene):
        self.index += 1
        name = f'frame-{self.index:04d}'
        cv2.imwrite(str(self.directory / (name + '.png')), frame)
        data = {'scene': scene, 'size': [frame.shape[1], frame.shape[0]],
                'ocr': [{'text': t.text, 'score': t.score, 'box': t.box} for t in records]}
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

    def theme_catalog(self):
        if self.themes is None:
            self.themes=ThemeCatalog(ROOT/'assets/resource/base')
        return self.themes

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
        if scene=='UNKNOWN' and theme_page(image,self.theme_catalog()):
            scene='THEME_PACKS'
        name = self.journal.frame(image, records, scene)
        self.last_frame, self.last_scene = image.copy(), scene
        self.cache = (digest, records, scene, name)
        return records, scene, name

    def analyze(self, context, argv):
        params = json.loads(argv.custom_recognition_param or '{}')
        records, scene, frame = self.observe(context, argv.image)
        expected = params['scene']
        if scene != expected:
            return None
        mode = params.get('team_mode')
        if params.get('theme_mode'):
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

    def run(self, context, argv):
        params = json.loads(argv.custom_action_param or '{}')
        mode=params.get('mode')
        if mode in ('name','pack','weight'):
            team=self.recognition.team
            if team is None:return False
            if mode=='pack':
                pack=params.get('name','')
                if pack and pack not in self.recognition.theme_catalog().names:
                    raise ValueError('Unknown theme preference')
                self.recognition.pending_pack=pack
                return True
            if mode=='name':configured=replace(team,name=str(params.get('name',team.name)))
            else:
                if not self.recognition.pending_pack:return True
                weights=dict(team.pack_weights);weights[self.recognition.pending_pack]=params['weight']
                configured=replace(team,pack_weights=tuple(weights.items()))
            store=ProfileStore(Path(os.environ.get('MAALIMBUS_DATA_PATH',ROOT/'config'))/'user-team-profiles.json')
            teams=list(store.load())
            index=next(i for i,t in enumerate(teams) if t.slot==team.slot)
            teams[index]=configured;store.save(teams)
            self.recognition.team=configured
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

    def run(self,context,argv):
        try:
            wait_job(context.tasker.controller.post_screencap(),timeout=5)
        except (TimeoutError,RuntimeError):return False
        records,scene,frame=self.recognition.observe(context,context.tasker.controller.cached_image)
        self.recognition.journal.record('theme_drag_observation',frame=frame,scene=scene,
            selected=False,verified_clear=False,
            reason='fresh_observation_only_map_postcondition_not_implemented')
        return True


class InputPreflight(CustomAction):
    def __init__(self,recognition):
        super().__init__(); self.recognition=recognition

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

    def run(self, context, argv):
        params = json.loads(argv.custom_action_param or '{}')
        self.recognition.journal.record('terminal', reason=params['reason'],
                                       last_scene=self.recognition.last_scene,
                                       verified_clear=False)
        return False
