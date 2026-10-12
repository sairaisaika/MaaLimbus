"""Native price evidence for the shop's regular Refresh caption."""
import re
from maa.pipeline import JRecognitionType,JOCR
from .vision import Text,find


def repair_purchased_badges(native,image,records):
    """Purchased is drawn above retained art; full-page OCR can omit it."""
    from .shop_vision import offers,shelf_tokens
    size=(image.shape[1],image.shape[0]);sx,sy=size[0]/1920,size[1]/1080
    result=list(records);proof=[]
    for offer in offers(shelf_tokens(records),size):
        if offer.purchased:continue
        x,y,w,h=offer.price_box;px=x+w/2;py=y+h/2
        crops=((round(px-70*sx),round(py-153*sy),round(140*sx),round(42*sy)),
               (round(px-74*sx),round(py-157*sy),round(148*sx),round(50*sy)))
        readings=[]
        for roi in crops:
            d=native(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,expected=[r'^Purchased$'],threshold=.9),image)
            found=d.filtered_results if d is not None and d.hit else []
            readings.append(found)
            proof.append(dict(purpose='shop_purchased_badge',name=offer.name,roi=list(roi),threshold=.9,
                results=[dict(text=r.text,score=r.score) for r in found]))
        if all(len(r)==1 and r[0].text.strip()=='Purchased' and r[0].score>=.9 for r in readings):
            result.append(Text('Purchased',crops[0],min(r[0].score for r in readings)))
    return result,proof


def repair_purchase_balances(native,image,records):
    """Actual Purchase E.G.O Gifts balance pair; two independent reads each."""
    from .shop_vision import native_purchase_dialog
    size=(image.shape[1],image.shape[0])
    if native_purchase_dialog(records,size) is None:return records,[]
    sx,sy=size[0]/1920,size[1]/1080
    result=list(records);proof=[]
    for name,crops in (('before',((1230,236,53,34),(1228,234,59,39))),
                       ('after',((1305,235,57,35),(1303,233,61,40)))):
        readings=[]
        for source in crops:
            roi=tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(source))
            d=native(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,expected=[r'^\d{1,4}$'],threshold=.9),image)
            found=d.filtered_results if d is not None and d.hit else []
            readings.append(found)
            proof.append(dict(purpose='shop_purchase_balance_'+name,roi=list(roi),threshold=.9,
                results=[dict(text=r.text,score=r.score) for r in found]))
        if (all(len(r)==1 and r[0].score>=.9 and re.fullmatch(r'\d{1,4}',r[0].text.strip()) for r in readings)
                and int(readings[0][0].text)==int(readings[1][0].text)):
            source=crops[0];roi=tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(source))
            # The full OCR combines both amounts into27072563; preserve it as
            # raw evidence and add only actual native numeric crop results.
            result.append(Text(str(int(readings[0][0].text)),roi,min(r[0].score for r in readings)))
    return result,proof


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
