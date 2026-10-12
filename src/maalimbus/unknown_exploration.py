"""Bounded navigation probes and immutable human-review bundles.

Page identity can be unknown while a native Close/Back control is known. These
probes never approve spending, choices, receipts, or their own training labels.
"""
import hashlib
import re
import shutil
from pathlib import Path
from .storage import read_json, write_json


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def proof(path):
    import cv2
    path=Path(path).resolve(); record=read_json(path)
    png=path.with_suffix('.png'); image=cv2.imread(str(png))
    if image is None or digest(png)!=record.get('image_sha256'):
        raise ValueError('Exploration frame pixels/hash not proven')
    if record.get('size')!=[image.shape[1],image.shape[0]]:
        raise ValueError('Exploration frame geometry not proven')
    return dict(record=str(path),record_sha256=digest(path),
                image=str(png),image_sha256=digest(png)),record


def candidates(record):
    # Resource dialogs and destructive/run-exit controls require their normal
    # transaction, even when the surrounding page cannot yet be classified.
    text=' '.join(str(t.get('text','')) for t in record.get('ocr',[]))
    if re.search(r'enkephalin|lunacy|refill|give\s*up|to\s*window|claim|rewards? acquired|purchase|confirm|convert',text,re.I):
        return []
    size=record.get('size')
    if not isinstance(size,list) or len(size)!=2:return []
    w,h=size; rows=[]
    if record.get('scene')=='MAP':
        from .map_vision import map_header
        from .vision import Text
        header=map_header([Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])],size)
        if header and header.floor is not None and header.pack:
            # This gesture moves only the identified map viewport. Both ends
            # stay above the party strip and away from header/side controls.
            for name,dx,dy in (('down',0,.21),('left',-.20,0),('right',.20,0)):
                rows.append(dict(kind='map_viewport_pan_'+name,action='swipe',
                    box=[round(w*.49),round(h*.55),round(w*.02),round(h*.03)],
                    to_box=[round(w*(.49+dx)),round(h*(.55+dy)),round(w*.02),round(h*.03)],
                    teacher='native_map_header_and_floor',score=1.0,floor=header.floor,pack=header.pack))
            return rows
    closer=record.get('overlay_dismissal') or {}
    if closer.get('kind') in ('tutorial_book','identity_details','unclassified_overlay_return') and closer.get('native_score',0)>=.92:
        rows.append(dict(kind='matched_header_return',box=closer['box'],
                         teacher=closer.get('template'),score=closer['native_score']))
    for label in ('Close','Back','Return','閉じる','戻る','关闭','返回'):
        hits=[t for t in record.get('ocr',[]) if t.get('text','').strip()==label
              and t.get('score',0)>=.95 and len(t.get('box',[]))==4
              and t['box'][1]+t['box'][3]<=h*.22]
        if len(hits)==1:
            rows.append(dict(kind='native_header_'+label,box=list(hits[0]['box']),
                             teacher='native_ocr',score=hits[0]['score']))
    return [r for r in rows if all(type(v) is int for v in r['box'])
            and r['box'][2]>0 and r['box'][3]>0
            and r['box'][0]>=0 and r['box'][1]>=0
            and r['box'][0]+r['box'][2]<=w and r['box'][1]+r['box'][3]<=h]


class Exploration:
    def __init__(self,path,review_root,scope):
        self.path=Path(path);self.review_root=Path(review_root);self.scope=scope
        self.data=read_json(path) if self.path.exists() else dict(version=1,scope=scope,attempts=[],pending=None)
        if self.data.get('version')!=1 or self.data.get('scope')!=scope:
            raise ValueError('Exploration scope differs; preserve its evidence')

    def choose(self,record):
        recent=[]
        for item in reversed(self.data['attempts']):
            if item.get('success') or item.get('episode_resolved'):break
            recent.append(item)
        if self.data.get('pending') or len(recent)>=3:return None
        used={a['candidate']['kind'] for a in recent}
        return next((c for c in candidates(record) if c['kind'] not in used),None)

    def reserve(self,frame,candidate,point,delay,end=None):
        before,record=proof(frame)
        if self.data.get('pending') or candidate!=self.choose(record):
            raise ValueError('Exploration candidate absent, repeated or exhausted')
        x,y,w,h=candidate['box']
        if not (x<=point[0]<x+w and y<=point[1]<y+h and 350<=delay<=750):
            raise ValueError('Exploration input outside verified control')
        if candidate.get('action')=='swipe':
            ex,ey,ew,eh=candidate['to_box']
            if end is None or not (ex<=end[0]<ex+ew and ey<=end[1]<ey+eh):
                raise ValueError('Map pan must end inside its bounded canvas region')
        entry=dict(candidate=candidate,before=before,point=list(point),delay_ms=delay,
                   input_attempted=True,successor=None,reviewed=False)
        if end is not None:entry['end']=list(end)
        self.data['attempts'].append(entry);self.data['pending']=len(self.data['attempts'])-1
        write_json(self.path,self.data)

    def finish(self,frame,page):
        index=self.data.get('pending')
        if index is None:return None
        entry=self.data['attempts'][index]
        # Restart may observe a successor, but it cannot replay an attempted input.
        if any(digest(entry['before'][key])!=entry['before'][key+'_sha256'] for key in ('record','image')):
            raise ValueError('Exploration original proof changed; preserve pending')
        after,record=proof(frame)
        if page!=record.get('scene') and record.get('scene')!='UNKNOWN':
            raise ValueError('Exploration successor label not independently observed')
        changed=after['image_sha256']!=entry['before']['image_sha256']
        success=changed and page not in ('UNKNOWN','BATTLE_WAIT','CONNECTING')
        if entry['candidate'].get('action')=='swipe':
            # Pixel movement confirms panning, not arrival at a node. Three
            # pans remain the limit until an independently named panel opens.
            success=changed and page=='NODE_PANEL'
        entry.update(successor=after,page_after=page,changed=changed,success=success)
        key=hashlib.sha256((self.scope+entry['before']['record_sha256']+after['record_sha256']).encode()).hexdigest()
        destination=self.review_root/key;destination.mkdir(parents=True,exist_ok=True)
        for prefix,item in (('before',entry['before']),('after',after)):
            for field,suffix in (('record','.json'),('image','.png')):
                target=destination/(prefix+suffix)
                if target.exists() and digest(target)!=item[field+'_sha256']:
                    raise ValueError('Conflicting exploration review proof')
                if not target.exists():shutil.copyfile(item[field],target)
        manifest=dict(version=1,scope=self.scope,attempt=entry,
                      proposed_label='return_overlay_to_'+page if success else 'unresolved_navigation',
                      teacher='native_successor_after_bounded_navigation',reviewed=False,
                      training_eligible=False,input_authorized=False,
                      review_file='review.json',success=success)
        write_json(destination/'proposal.json',manifest)
        (destination/'trace.log').write_text(
            'Bounded native navigation\nControl: '+entry['candidate']['kind']+
            '\nAfter: '+page+'\nSuccess: '+str(success)+'\n',encoding='utf-8')
        if not (destination/'review.json').exists():
            write_json(destination/'review.json',dict(status='pending',approved=False,corrected_label=None,notes=''))
        self.data['pending']=None
        write_json(self.path,self.data)
        return dict(proposal=str(destination/'proposal.json'),success=success,changed=changed,
                    training_eligible=False,input_authorized=False)

    def resolve_episode(self,frame,page):
        if self.data.get('pending') is not None or not self.data['attempts']:return
        last=self.data['attempts'][-1]
        if last.get('success') or last.get('episode_resolved'):return
        if page not in ('NODE_PANEL','BATTLE_HUD','SHOP','THEME_PACKS','HOME'):return
        evidence,record=proof(frame)
        if record.get('scene')!=page:return
        # A later normal task input may resolve the episode. Do not relabel
        # the earlier pan as an action that directly opened that page.
        last.update(episode_resolved=True,resolution_page=page,resolution=evidence,
                    resolved_via_subsequent_task_action=True)
        write_json(self.path,self.data)


def queue_trial(frame,offer,scope,root):
    source,record=proof(frame)
    key=hashlib.sha256((scope+source['record_sha256']+offer.title).encode()).hexdigest()
    folder=Path(root)/'trials'/key;folder.mkdir(parents=True,exist_ok=True)
    for field,suffix in (('record','.json'),('image','.png')):
        destination=folder/('frame'+suffix)
        if destination.exists() and digest(destination)!=source[field+'_sha256']:
            raise ValueError('Conflicting trial review pixels')
        if not destination.exists():shutil.copyfile(source[field],destination)
    proposal=dict(version=1,scope=scope,source=source,title=offer.title,
        observed_level=offer.trial.level,printed_trial=offer.unpriced,
        proposed_label='unclassified_enemy_trial',teacher='native_ocr',
        reviewed=False,training_eligible=False,input_authorized=False)
    template=re.sub(r'\d+(?:\.\d+)?','#',offer.unpriced.casefold())
    template=re.sub(r'\s+',' ',template).strip()
    proposal.update(text_template=template,
        proposed_group='enemy_trial_text_'+hashlib.sha256(template.encode()).hexdigest()[:16],
        grouping_teacher='normalized_native_text_not_effect_interpretation')
    path=folder/'proposal.json'
    if not path.exists():write_json(path,proposal)
    if not (folder/'review.json').exists():
        write_json(folder/'review.json',dict(status='pending',approved=False,corrected_label=None,notes=''))
    (folder/'trace.log').write_text('Native trial reading queued; original effect remains unpriced.\n'
        +'Source: '+source['record']+'\nGift: '+offer.title+'\nText: '+offer.unpriced+'\n',encoding='utf-8')
    return dict(proposal=str(path),proposal_sha256=digest(path),training_eligible=False)
