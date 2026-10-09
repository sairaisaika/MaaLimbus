"""Floor-gift candidates: bounded local labels/icons and per-column ownership.

LALC mirror_select_floor_ego_gift (431b432) supplies keyword/icon provenance
and local title/ownership strips. No season/cover or whole-screen template is used.
Unidentified/ambiguous candidates do not receive a speculative score.
"""
from dataclasses import dataclass
import difflib
import hashlib
import json
from pathlib import Path
import re

import cv2
import numpy as np

from .policies import Gift, rank_gifts
from .vision import Text, find, inset_box


def normalized(text):
    return re.sub(r'[^\w]', '', text.casefold())


class GiftCatalog:
    def __init__(self, root):
        self.root = Path(root).resolve()
        data = json.loads((self.root/'gift-catalog.json').read_text(encoding='utf-8'))
        if data.get('version') != 1 or data.get('reference_width') != 1280:
            raise ValueError('Unsupported gift catalog')
        self.entries = {g['name']:g for g in data['gifts']}
        if len(self.entries) != len(data['gifts']):
            raise ValueError('Duplicate gift identity')
        # Independently observed titles do not inherit LALC assets or keywords.
        # Require exact normalized text; a partial title cannot establish them.
        self.observed_names = set()
        observed = self.root/'gift-observed-catalog.json'
        if observed.exists():
            extra = json.loads(observed.read_text(encoding='utf-8'))
            if extra.get('version') != 1:
                raise ValueError('Unsupported observed gift catalog')
            for entry in extra['gifts']:
                if (entry['name'] in self.entries or entry['keywords'] or entry['icons']
                        or not re.fullmatch(r'[a-f0-9]{64}', entry['evidence_sha256'])):
                    raise ValueError('Invalid observed gift provenance')
                self.entries[entry['name']] = entry
                self.observed_names.add(entry['name'])
        self.icons = []
        for entry in self.entries.values():
            for icon in entry['icons']:
                path = (self.root/icon['path']).resolve()
                if not path.is_relative_to(self.root) or hashlib.sha256(path.read_bytes()).hexdigest() != icon['sha256']:
                    raise ValueError('Gift icon provenance/integrity mismatch')
                frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError('Invalid gift icon')
                self.icons.append((entry['name'], frame))

    def text_identity(self, text):
        target = normalized(text)
        scores = sorted([(difflib.SequenceMatcher(None,target,normalized(name)).ratio(),name)
                         for name in self.entries
                         if name not in self.observed_names or target == normalized(name)],reverse=True)
        if not scores or scores[0][0] < .93:
            return None
        if len(scores)>1 and scores[0][0]-scores[1][0]<.04:
            return None
        return scores[0][1]

    def icon_identity(self, crop, width):
        if crop.size == 0 or float(crop.std()) < 1:
            return None
        gray = cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
        scores = {}
        for name, icon in self.icons:
            # Small scale tolerance accommodates the crop source without using covers.
            for factor in (.95,1.0,1.05):
                scale = width/1280*factor
                template = cv2.resize(icon,None,fx=scale,fy=scale)
                if template.shape[0]>gray.shape[0] or template.shape[1]>gray.shape[1]:
                    continue
                match = cv2.matchTemplate(gray,cv2.cvtColor(template,cv2.COLOR_BGR2GRAY),cv2.TM_CCOEFF_NORMED)
                finite = match[np.isfinite(match)]
                score = float(finite.max()) if finite.size else -1
                scores[name] = max(score,scores.get(name,-1))
        ranked = sorted([(score,name) for name,score in scores.items()],reverse=True)
        if not ranked or ranked[0][0]<.91 or (len(ranked)>1 and ranked[0][0]-ranked[1][0]<.025):
            return None
        return ranked[0][1]


@dataclass(frozen=True)
class GiftCandidate:
    gift: Gift
    box: tuple
    evidence: str


def floor_candidates(frame, records, locale, catalog):
    h,w = frame.shape[:2]
    labels = sorted(find(records,locale['acquire_gift'],(.06,.13,.95,.26),(w,h),.8),
                    key=lambda r:r.box[0]+r.box[2]/2)
    if not 1<=len(labels)<=6:
        return []
    centers = [(r.box[0]+r.box[2]/2)/w for r in labels]
    if any(b-a<.10 for a,b in zip(centers,centers[1:])):
        return [] # Duplicate/overlapping labels are not separate choices.
    bounds = [.04]+[(a+b)/2 for a,b in zip(centers,centers[1:])]+[.97]
    candidates = []
    for index,label in enumerate(labels):
        left,right = bounds[index:index+2]
        titles = find(records,r'.+', (left,.245,right,.33),(w,h),.8)
        names = {catalog.text_identity(t.text) for t in titles}
        names.discard(None)
        # The gift icon is below its title, within this candidate's column.
        crop = frame[round(.31*h):round(.66*h),round(left*w):round(right*w)]
        icon_name = catalog.icon_identity(crop,w)
        if len(names)>1 or (icon_name and names and icon_name not in names):
            continue
        name = next(iter(names)) if names else icon_name
        if name is None:
            continue
        owned = bool(find(records,locale['owned_gift'],(left,.13,right,.25),(w,h),.8))
        entry = catalog.entries[name]
        candidates.append(GiftCandidate(Gift(name,frozenset(entry['keywords']),owned=owned),
                                        inset_box(label.box), 'title_and_icon' if names and icon_name else 'title' if names else 'icon'))
    return candidates


def recommend(candidates, team):
    ranking = rank_gifts([c.gift for c in candidates],team)
    if not ranking:
        return None, []
    # Duplicate identities use the leftmost visible candidate, not an arbitrary dict overwrite.
    target = min((c for c in candidates if c.gift.name==ranking[0]['name']),key=lambda c:c.box[0])
    return target, ranking


def search_owned_names(frame,records,catalog):
    """Per-tile Owned label plus exposed lower icon, excluding its label overlay."""
    h,w=frame.shape[:2]
    if (w,h)!=(1920,1080):return []
    gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    names=[]
    for label in find(records,r'^Owned$',(.06,.30,.59,.85),(w,h),.9):
        x,y,bw,bh=label.box
        crop=gray[y+30:y+124,max(0,x-22):x+118]
        scores={}
        for name,icon in catalog.icons:
            for factor in (.95,1.0,1.05):
                scaled=cv2.resize(icon,None,fx=1.5*factor,fy=1.5*factor)
                template=cv2.cvtColor(scaled[round(scaled.shape[0]*.25):],cv2.COLOR_BGR2GRAY)
                if template.shape[0]>crop.shape[0] or template.shape[1]>crop.shape[1]:continue
                score=float(cv2.matchTemplate(crop,template,cv2.TM_CCOEFF_NORMED).max())
                if np.isfinite(score):scores[name]=max(score,scores.get(name,-1))
        ranking=sorted(((v,k) for k,v in scores.items()),reverse=True)
        if ranking and ranking[0][0]>=.82 and (len(ranking)==1 or ranking[0][0]-ranking[1][0]>=.12):
            names.append(dict(name=ranking[0][1],score=ranking[0][0],owned_label=label.box))
    return names
