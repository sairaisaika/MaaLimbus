"""Native currency/sign/cost evidence for the retained English reward layout.

Recognizing an offer does not authorize spending or establish received rewards.
"""
import re
from .vision import find

def page_anchors(records,size):
    gates=[(r'^Exploration Reward$',(.39,.12,.60,.20)),
           (r'^Floor 5$',(.24,.56,.31,.61)),
           (r'^\[HARD\]$',(.24,.59,.31,.64)),
           (r'^7/7$',(.25,.62,.31,.69)),
           (r'^To Window$',(.43,.72,.56,.79)),
           (r'^Claim$',(.62,.72,.71,.79)),
           (r'^Weekly$',(.22,.29,.31,.35)),
           (r'^Bonuses$',(.22,.33,.31,.38))]
    return all(len(find(records,p,band,size,.9))==1 for p,band in gates)

def combine_evidence(readings):
    """All independently gated native results must be unique and agree."""
    digits=[]
    for purpose in ('currency','deduction','cost_digit_a','cost_digit_b','weekly_count'):
        rows=[r for r in readings if r['purpose']==purpose]
        if len(rows)!=1 or len(rows[0]['results'])!=1:return None
        result=rows[0]['results'][0]
        if result['score']<(.95 if purpose in ('currency','deduction') else .9):return None
        if purpose.startswith('cost_digit'):
            text=result.get('text','').strip()
            if not re.fullmatch(r'[1-9]\d?',text):return None
            digits.append(int(text))
        elif purpose=='weekly_count':
            match=re.fullmatch(r'([0-3])/3',result.get('text','').strip())
            if not match:return None
            weekly=int(match[1])
    if digits[0]!=digits[1]:return None
    return dict(currency='enkephalin_modules',cost=digits[0],weekly=weekly)

def observe_native(context,image,records):
    from maa.pipeline import JOCR,JRecognitionType,JTemplateMatch
    size=(image.shape[1],image.shape[0])
    if size!=(1920,1080) or not page_anchors(records,size):return None,[]
    evidence=[]
    for purpose,template,roi in (
        ('currency','reward/module-currency.png',(1370,786,65,63)),
        ('deduction','reward/deduction-sign.png',(1429,805,21,30))):
        detail=context.run_recognition_direct(JRecognitionType.TemplateMatch,
            JTemplateMatch(template=[template],roi=roi,threshold=[.95]),image)
        results=detail.filtered_results if detail is not None and detail.hit else []
        evidence.append(dict(purpose=purpose,roi=list(roi),template=template,
            results=[dict(score=r.score) for r in results]))
    for purpose,roi,expected in (
        ('cost_digit_a',(1448,793,28,45),r'^[1-9]\d?$'),
        ('cost_digit_b',(1444,790,36,50),r'^[1-9]\d?$'),
        ('weekly_count',(650,340,88,72),r'^[0-3]/3$')):
        detail=context.run_recognition_direct(JRecognitionType.OCR,
            JOCR(roi=roi,only_rec=True,expected=[expected],threshold=.9),image)
        results=detail.filtered_results if detail is not None and detail.hit else []
        evidence.append(dict(purpose=purpose,roi=list(roi),only_rec=True,
            results=[dict(text=r.text,score=r.score) for r in results]))
    return combine_evidence(evidence),evidence
