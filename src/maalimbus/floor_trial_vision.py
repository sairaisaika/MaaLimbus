"""Independent narrow native reads of Mounting Trials level badges."""
import re
from maa.pipeline import JRecognitionType, JOCR
from .vision import Text, find
from .reward_vision import gift_cards


def repair_levels(native, image, records):
    size = (image.shape[1], image.shape[0])
    cards = gift_cards(records, size)
    if not 1 <= len(cards) <= 6:
        return records, []
    sx, sy = size[0]/1920, size[1]/1080
    centers = [b[0]+b[2]/2 for b in cards]
    bounds = [0]+[(a+b)/2 for a,b in zip(centers,centers[1:])]+[size[0]]
    result, evidence = list(records), []
    for index, center in enumerate(centers):
        left, right = bounds[index]/size[0], bounds[index+1]/size[0]
        # The card's own full heading anchors a read; no pending-state/default level.
        if len(find(records, r'^Mounting Trials$', (left,.57,right,.62),size,.9)) != 1:
            continue
        if len(find(records, r'^\+\s*\d+$', (left,.62,right,.67),size,.85)) == 1:
            continue
        readings=[]
        for dx,width in ((-161,63),(-151,48)):
            roi=tuple(round(v) for v in (center+dx*sx,664*sy,width*sx,47*sy))
            detail=native(JRecognitionType.OCR,
                          JOCR(roi=roi,only_rec=True,expected=[r'^\+\s*\d{1,2}$'],threshold=.9),image)
            found=detail.filtered_results if detail is not None and detail.hit else []
            readings.append((roi,found))
            evidence.append(dict(purpose='mounting_trial_level',card=index+1,roi=list(roi),
                                 threshold=.9,results=[dict(text=r.text,score=r.score) for r in found]))
        a,b=readings[0][1],readings[1][1]
        if not (len(a)==len(b)==1 and a[0].score>=.9 and b[0].score>=.9):
            continue
        numbers=[re.fullmatch(r'\+\s*(\d{1,2})', f[0].text.strip()) for _,f in readings]
        if not all(numbers) or numbers[0][1]!=numbers[1][1] or not 1<=int(numbers[0][1])<=30:
            continue
        roi=readings[0][0];x,y,w,h=roi
        result=[t for t in result if not (x<=t.box[0]+t.box[2]/2<=x+w and y<=t.box[1]+t.box[3]/2<=y+h)]
        result.append(Text('+'+numbers[0][1],roi,min(a[0].score,b[0].score)))
    return result,evidence
