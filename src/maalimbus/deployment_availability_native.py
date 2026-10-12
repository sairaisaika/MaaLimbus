"""Current encounter eligibility: native HP zero plus a desaturated full card.

This is a page reading, never an account ownership or model-generated label.
The counter must independently account for every unavailable card.
"""
import cv2
from maa.pipeline import JOCR,JRecognitionType
from .team_vision import participants


def read_availability(native,image,records,boxes):
    if image.shape[:2]!=(1080,1920) or len(boxes)!=12 or not all(boxes):return []
    count=participants(records,(1920,1080))
    if not count or count[1]>=12:return []
    cards=[];unavailable=[]
    for index,box in enumerate(boxes,1):
        x,y,w,h=map(int,box);crop=image[y:y+h,x:x+w]
        if crop.size==0:return []
        hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
        color=float((hsv[:,:,1]>60).mean())
        neutral=float(((hsv[:,:,1]<35)&(hsv[:,:,2]>100)).mean())
        reads=[];zero=False
        if color<.03 and neutral>.25:
            for roi in ((124+(index-1)*116,1020,25,32),(126+(index-1)*116,1021,21,30)):
                d=native(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,expected=[r'^0$'],threshold=.9),image)
                rows=list(d.filtered_results) if d is not None and d.hit else []
                reads.append(dict(roi=list(roi),results=[dict(text=r.text,score=r.score) for r in rows]))
            zero=all(len(r['results'])==1 and r['results'][0]['text'].strip()=='0'
                     and r['results'][0]['score']>=.9 for r in reads)
            if zero:unavailable.append(index)
        cards.append(dict(card=index,color_fraction=color,bright_neutral_fraction=neutral,
                          hp_crops=reads,hp_zero_agreement=zero))
    # A missing or ambiguous card cannot silently become available or deceased.
    accepted=(12-len(unavailable)==count[1] and bool(unavailable)
              and all(c['hp_zero_agreement'] or c['color_fraction']>.3 for c in cards))
    return [dict(purpose='deployment_availability',accepted=accepted,participants=list(count),
                 unavailable=unavailable if accepted else [],cards=cards,teacher='native_hp_and_card_pixels')]
