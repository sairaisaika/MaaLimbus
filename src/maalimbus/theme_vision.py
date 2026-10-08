"""Local fixed glyph geometry + title OCR, independent of theme artwork.

Pinned LALC get_save_theme_packs supplies the 170x330 card offsets and title
band. Its theme-selection weights are retained as reference data, not silently
applied. We do not choose an unidentified NEW pack or refresh without a cost
policy. Maa Pipeline owns the drag; this module never calls an input API.
"""
from dataclasses import dataclass
import difflib
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from .gift_vision import normalized
from .vision import Text,find
import re


def selection_floor(records,size):
    """Page identity only, independent of tilted covers and mode glyphs.

    Does not prove Hard/Normal and grants no drag or difficulty switch.
    """
    headers=find(records,r'^SELECT\s*FLOOR\s*[1-5]\s*THEME\s*PACK$',(.38,.13,.63,.20),size,.9)
    refresh=find(records,r'^Refresh$',(.79,0,.91,.10),size,.9)
    search=find(records,r'^Pack Search$',(.10,0,.21,.10),size,.9)
    if len(headers)!=1 or len(refresh)!=1 or len(search)!=1:return None
    return int(re.search(r'FLOOR\s*([1-5])',headers[0].text,re.I)[1])


@dataclass(frozen=True)
class PackCandidate:
    name: str | None
    box: tuple[int,int,int,int]
    new: bool = False


class ThemeCatalog:
    def __init__(self,root,filename='theme-catalog.json'):
        self.root=Path(root).resolve()
        data=json.loads((self.root/filename).read_text(encoding='utf-8'))
        if data.get('version')!=1 or (data.get('reference_width'),data.get('reference_height'))!=(1280,720):
            raise ValueError('Unsupported theme catalog')
        self.names=tuple(entry['name'] for entry in data['names'])
        if len(set(self.names))!=len(self.names):
            raise ValueError('Duplicate theme name')
        self.glyphs={}
        for key,entry in data['glyphs'].items():
            path=(self.root/entry['path']).resolve()
            if not path.is_relative_to(self.root) or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
                raise ValueError('Theme glyph provenance/integrity mismatch')
            glyph=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
            if glyph is None: raise ValueError('Invalid theme glyph')
            self.glyphs[key]=glyph

    def identity(self,text):
        target=normalized(text)
        ranks=sorted([(difflib.SequenceMatcher(None,target,normalized(n)).ratio(),n)
                      for n in self.names],reverse=True)
        if not ranks or ranks[0][0]<.93 or (len(ranks)>1 and ranks[0][0]-ranks[1][0]<.04):
            return None
        return ranks[0][1]

    def matches(self,image,key,roi):
        h,w=image.shape[:2]
        x0,y0,x1,y1=[round(v*s) for v,s in zip(roi,(w,h,w,h))]
        crop=cv2.cvtColor(image[y0:y1,x0:x1],cv2.COLOR_BGR2GRAY)
        found=[]
        for factor in (.97,1.,1.03):
            scale=w/1280*factor
            glyph=cv2.resize(self.glyphs[key],None,fx=scale,fy=scale)
            gh,gw=glyph.shape
            if gh>crop.shape[0] or gw>crop.shape[1]: continue
            scores=cv2.matchTemplate(crop,glyph,cv2.TM_CCOEFF_NORMED)
            # At most six candidates; adjacent template peaks must not become cards.
            for _ in range(6):
                _,score,_,pos=cv2.minMaxLoc(scores)
                if not np.isfinite(score) or score<.92: break
                x,y=pos
                found.append((float(score),(x+x0,y+y0,gw,gh)))
                scores[max(0,y-gh):y+gh,max(0,x-gw):x+gw]=-1
        unique=[]
        for score,box in sorted(found,reverse=True):
            cx,cy=box[0]+box[2]/2,box[1]+box[3]/2
            if all(abs(cx-(b[0]+b[2]/2))>20*w/1280 or abs(cy-(b[1]+b[3]/2))>20*w/1280 for b in unique):
                unique.append(box)
        return sorted(unique)


def theme_page(image,catalog,records=(),locale=None):
    size=(image.shape[1],image.shape[0])
    # Header + two independent controls prove this page. Strict literal mode OCR
    # is sufficient without a seasonal pack-detail glyph, but conflicts refuse.
    if selection_floor(records,size) is not None:
        hard_text=find(records,r'^HARD$',(.61,0,.83,.13),size,.9)
        normal_text=find(records,r'^NORMAL$',(.61,0,.83,.13),size,.9)
        if len(hard_text)+len(normal_text)>1:return None
        if len(hard_text)+len(normal_text)==1:
            other='normal_mode' if hard_text else 'hard_mode'
            if catalog.matches(image,other,(.61,0,.83,.13)):return None
            return 'hard' if hard_text else 'normal'
    details=catalog.matches(image,'theme_pack_detail',(.06,.14,.96,.36))
    hard=catalog.matches(image,'hard_mode',(.61,0,.83,.13))
    normal=catalog.matches(image,'normal_mode',(.61,0,.83,.13))
    search=catalog.matches(image,'pack_search',(.76,0,.93,.13))
    text_controls=(locale is not None
        and len(find(records,locale.get('theme_floor_select',r'(?!)'),(.38,.13,.63,.20),(image.shape[1],image.shape[0]),.85))==1
        and len(find(records,locale.get('theme_refresh',r'(?!)'),(.79,0,.91,.10),(image.shape[1],image.shape[0]),.85))==1)
    if not 1<=len(details)<=6 or (len(search)!=1 and not text_controls):
        return None
    size=(image.shape[1],image.shape[0])
    hard_text=find(records,r'^HARD[\s/]*$',(.61,0,.83,.13),size,.9)
    normal_text=find(records,r'^[\s/]*NORMAL$',(.61,0,.83,.13),size,.9)
    if len(hard_text)+len(normal_text)>1:return None
    text_mode=('hard' if hard_text else 'normal') if len(hard_text)+len(normal_text)==1 else None
    if len(hard)+len(normal)==1:
        glyph_mode='hard' if hard else 'normal'
        return glyph_mode if text_mode in (None,glyph_mode) else None
    if not hard and not normal and text_controls:return text_mode
    return None


def pack_candidates(image,records,catalog):
    h,w=image.shape[:2]; scale=w/1280
    details=catalog.matches(image,'theme_pack_detail',(.06,.14,.96,.36))
    if not details and 'theme_card_clip' in catalog.glyphs and selection_floor(records,(w,h)) is not None:
        clips=catalog.matches(image,'theme_card_clip',(.16,.21,.83,.30))
        if not 1<=len(clips)<=6:return []
        if max(y for x,y,bw,bh in clips)-min(y for x,y,bw,bh in clips)>8*scale:return []
        # This fixed hanging clip exposes the center of each settled card. Map
        # it to the card-local rectangle; titles still establish pack identity.
        cards=[]
        for x,y,bw,bh in clips:
            cx=x+bw/2
            box=(round(cx-90*scale),round(y+10*scale),round(180*scale),round(340*scale))
            if any(max(box[0],b[0])<min(box[0]+box[2],b[0]+b[2]) for b in cards):return []
            cards.append(box)
        return _named_cards(image,records,catalog,cards)
    new=catalog.matches(image,'mirror_theme_pack_new',(.06,.13,.96,.36))
    cards=[]
    for gx,gy,gw,gh in details:
        cx,cy=gx+gw/2,gy+gh/2
        box=(round(cx-135*scale),round(cy-35*scale),round(170*scale),round(330*scale))
        x,y,bw,bh=box
        if x<0 or y<0 or x+bw>w or y+bh>h:
            return []
        if any(max(x,b[0])<min(x+bw,b[0]+b[2]) for b in cards):
            return []
        cards.append(box)
    return _named_cards(image,records,catalog,cards,new)


def _named_cards(image,records,catalog,cards,new=()):
    h,w=image.shape[:2];scale=w/1280
    candidates=[]
    for x,y,bw,bh in cards:
        # Maa's detector expands short labels by a few pixels. Permit that padding
        # while retaining a card-local center and refusing adjacent/spilled names.
        padding=8*scale
        texts=[t for t in records if t.score>=.8 and x-padding<=t.box[0] and t.box[0]+t.box[2]<=x+bw+padding
               and x<=t.box[0]+t.box[2]/2<=x+bw
               and y+235*scale<=t.box[1]+t.box[3]/2<=y+300*scale]
        texts.sort(key=lambda t:t.box[1]+t.box[3]/2)
        lines=[]
        for text in texts:
            cy=text.box[1]+text.box[3]/2
            if lines and abs(cy-lines[-1][0])<=12*scale:
                lines[-1][1].append(text)
            else:lines.append((cy,[text]))
        texts=[t for cy,line in lines for t in sorted(line,key=lambda t:t.box[0])]
        name=catalog.identity(' '.join(t.text for t in texts)) if texts else None
        is_new=any(x<=nx+nw/2<=x+bw and y<=ny+nh/2<=y+70*scale for nx,ny,nw,nh in new)
        candidates.append(PackCandidate(name,(x,y,bw,bh),is_new))
    # Duplicate titles are not sufficient evidence of distinct selectable identities.
    known=[c.name for c in candidates if c.name]
    if len(set(known))!=len(known):return []
    return candidates


def recommend_pack(candidates,team):
    weights=dict(team.pack_weights)
    ranked=[dict(name=c.name,weight=weights.get(c.name,10),box=c.box,
                 reason='team_weight' if c.name in weights else 'neutral_default')
            for c in candidates if c.name is not None and not c.new and weights.get(c.name,10)>0]
    ranked.sort(key=lambda r:(-r['weight'],r['box'][0]))
    return ranked[0] if ranked else None,ranked
