"""Independent narrow native turn reads, gated by the HUD's own captions."""
import re
from maa.pipeline import JRecognitionType,JOCR
from .vision import Text,find
from .battle_vision import auto_assign_buttons


def repair_turn(native,image,records):
    size=(image.shape[1],image.shape[0]);sx,sy=size[0]/1920,size[1]/1080
    if len(find(records,r'^TURN$',(.0,.06,.06,.13),size,.9))!=1 or auto_assign_buttons(records,size) is None:
        return records,[]
    proof=[];readings=[]
    for source in ((94,90,40,42),(93,89,42,43)):
        roi=tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(source))
        detail=native(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,expected=[r'^\d{1,3}$'],threshold=.9),image)
        found=detail.filtered_results if detail is not None and detail.hit else []
        readings.append(found);proof.append(dict(purpose='battle_turn_digit',roi=list(roi),threshold=.9,
            results=[dict(text=r.text,score=r.score) for r in found]))
    if not all(len(r)==1 and r[0].score>=.9 and re.fullmatch(r'\d{1,3}',r[0].text.strip()) for r in readings):
        return records,proof
    values=[int(r[0].text.strip()) for r in readings]
    if values[0]!=values[1] or values[0]<=0:return records,proof
    # Keep the raw record elsewhere in the observation; the new field contains
    # only actual agreeing reads. Do not borrow a pending turn or click result.
    result=[r for r in records if not (.035<=(r.box[0]+r.box[2]/2)/size[0]<=.081
                                      and .077<=(r.box[1]+r.box[3]/2)/size[1]<=.121)]
    result.append(Text(str(values[0]),tuple(round(v*(sx if i%2==0 else sy))
        for i,v in enumerate((94,90,40,42))),min(r[0].score for r in readings)))
    return result,proof
