"""Read the order glyph, independently of card artwork and OCR detection."""
from .team_vision import assignment_box
from .vision import Text

#: Three framings of one printed digit, as fractions of that card's assignment band. The
#: narrow window is the tightest one that still holds the glyph; a second framing with a
#: margin is what proves the reading, and the third keeps a tighter window because a single
#: alternative framing can lose a glyph the narrow one holds: the retained
#: evidence/runtime/packaged-mirror-20261012-101555/frame-0027 reads card 11's '7' in the
#: narrow window and nothing at all in the wider one, while
#: evidence/runtime/packaged-mirror-20261014-063205/frame-0103 reads card 11's '4' only
#: because a margin is kept. Two framings must read the same number before it is adopted, so
#: no single reading ever decides an order, and a card whose glyph no two framings agree on
#: keeps ``None`` instead of a guessed place.
CROP_BANDS = ((.20, .30, .51, .68), (.22, .32, .44, .63), (.16, .25, .60, .74))


def read_assignments(native,image,records,boxes):
    from maa.pipeline import JRecognitionType,JOCR
    result=list(records);proof=[]
    for index,box in enumerate(boxes,1):
        roi=assignment_box(box)
        if roi is None:continue
        x,y,w,h=roi
        crops=[(x+round(w*left),y+round(h*top),round(w*width),round(h*height))
               for left,top,width,height in CROP_BANDS]
        readings=[];numbers=[];proven=None
        for crop in crops:
            d=native(JRecognitionType.OCR,JOCR(roi=crop,only_rec=True,
                expected=[r'^(?:[1-9]|1[0-2])$'],threshold=.9),image)
            rows=[r for r in d.filtered_results if hasattr(r,'text') and r.score>=.9] if d and d.hit else []
            readings.append(dict(roi=list(crop),results=[dict(text=r.text,score=r.score) for r in rows]))
            if len(rows)==1 and rows[0].text.isdigit() and 1<=int(rows[0].text)<=12:
                number=int(rows[0].text)
                agreeing=[score for value,score in numbers if value==number]
                numbers.append((number,rows[0].score))
                if agreeing:
                    proven=(number,min([rows[0].score]+agreeing))
                    break
        result=[t for t in result if not (x<=t.box[0]+t.box[2]/2<=x+w and y<=t.box[1]+t.box[3]/2<=y+h)]
        if proven is not None:
            result.append(Text(str(proven[0]),roi,proven[1]))
        proof.append(dict(purpose='deployment_assignment',card=index,
            roi=list(roi),dual_crop=readings,agreement=proven is not None))
    return result,proof
