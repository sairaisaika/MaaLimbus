"""Read the order glyph, independently of card artwork and OCR detection."""
from .team_vision import assignment_box
from .vision import Text


def read_assignments(native,image,records,boxes):
    from maa.pipeline import JRecognitionType,JOCR
    result=list(records);proof=[]
    for index,box in enumerate(boxes,1):
        roi=assignment_box(box)
        if roi is None:continue
        x,y,w,h=roi
        crops=[(x+round(w*.20),y+round(h*.30),round(w*.51),round(h*.68)),
               (x+round(w*.23),y+round(h*.32),round(w*.44),round(h*.63))]
        reads=[];values=[]
        for crop in crops:
            d=native(JRecognitionType.OCR,JOCR(roi=crop,only_rec=True,
                expected=[r'^(?:[1-9]|1[0-2])$'],threshold=.9),image)
            rows=[r for r in d.filtered_results if hasattr(r,'text') and r.score>=.9] if d and d.hit else []
            reads.append(dict(roi=list(crop),results=[dict(text=r.text,score=r.score) for r in rows]))
            values.append((int(rows[0].text),rows[0].score) if len(rows)==1 and rows[0].text.isdigit() and 1<=int(rows[0].text)<=12 else None)
        result=[t for t in result if not (x<=t.box[0]+t.box[2]/2<=x+w and y<=t.box[1]+t.box[3]/2<=y+h)]
        if all(values) and values[0][0]==values[1][0]:
            result.append(Text(str(values[0][0]),roi,min(v[1] for v in values)))
        proof.append(dict(purpose='deployment_assignment',card=index,
            roi=list(roi),dual_crop=reads,agreement=bool(all(values) and values[0][0]==values[1][0])))
    return result,proof
