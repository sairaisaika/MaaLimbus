"""Native price evidence for the shop's regular Refresh caption."""
import re
from maa.pipeline import JRecognitionType,JOCR
from .vision import Text,find


def repair_refresh_cost(native,image,records):
    size=(image.shape[1],image.shape[0]);sx,sy=size[0]/1920,size[1]/1080
    label=find(records,r'^Refresh$',(.75,.13,.84,.19),size,.9)
    high=find(records,r'^\d{1,4}$',(.755,.195,.80,.245),size,.9)
    if len(label)!=1 or len(high)==1:return records,[]
    readings=[];proof=[]
    for source in ((1489,214,39,46),(1494,215,32,42)):
        roi=tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(source))
        d=native(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,expected=[r'^\d{1,4}$'],threshold=.9),image)
        found=d.filtered_results if d is not None and d.hit else []
        readings.append(found);proof.append(dict(purpose='shop_refresh_cost',roi=list(roi),threshold=.9,
            results=[dict(text=r.text,score=r.score) for r in found]))
    if not all(len(r)==1 and r[0].score>=.9 and re.fullmatch(r'\d{1,4}',r[0].text.strip()) for r in readings):
        return records,proof
    if not 0<int(readings[0][0].text)<=9999 or int(readings[0][0].text)!=int(readings[1][0].text):
        return records,proof
    result=[r for r in records if not (.755<=(r.box[0]+r.box[2]/2)/size[0]<=.80
                                     and .195<=(r.box[1]+r.box[3]/2)/size[1]<=.245)]
    result.append(Text(str(int(readings[0][0].text)),tuple(round(v*(sx if i%2==0 else sy))
                      for i,v in enumerate((1489,214,39,46))),min(r[0].score for r in readings)))
    return result,proof
