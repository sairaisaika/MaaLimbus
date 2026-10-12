"""Fast known guide dismissal using its own native-matched header arrow."""
from .vision import Text,find
from .overlay_vision import page_turn_arrows


def identity_details(record):
    if record.get('size')!=[1920,1080]:return False
    texts=[Text(x['text'],tuple(x['box']),x['score']) for x in record.get('ocr',[])]
    return all(len(find(texts,p,(.50,.22,.94,.42),record['size'],.9))==1
               for p in (r'^Summary$',r'^Skill$',r'^Sanity$',r'^Level Up$'))


def recognize(native,image,record):
    if record.get('size')!=[1920,1080]:return None
    is_details=identity_details(record)
    if record.get('scene')!='TUTORIAL' and not is_details:return None
    texts=[Text(x['text'],tuple(x['box']),x['score']) for x in record.get('ocr',[])]
    # The guide's title and page triangle are independent of inactive controls
    # visible behind it. Generic resource dialogs never pass this guide gate.
    headers=find(texts,r'^.{4,80}$',(.11,.02,.75,.11),record['size'],.9)
    arrows=page_turn_arrows(image)
    if not is_details and (len(headers)!=1 or not (arrows.get('next') or arrows.get('previous'))):return None
    from maa.pipeline import JRecognitionType,JTemplateMatch
    template='navigation/identity-details-back.png' if is_details else 'navigation/tutorial-back.png'
    detail=native(JRecognitionType.TemplateMatch,JTemplateMatch(
        template=[template],roi=(75,25,135,95),threshold=[.92]),image)
    if detail is None or not detail.hit or len(detail.filtered_results)!=1:return None
    match=detail.filtered_results[0];b=match.box
    if match.score<.92:return None
    box=list((b.x,b.y,b.w,b.h) if hasattr(b,'x') else b)
    return dict(kind='identity_details' if is_details else 'tutorial_book',box=box,native_score=match.score,
        title='Identity details' if is_details else headers[0].text,template=template,
        reason='close_known_overlay_with_its_own_header_arrow',input_authorized=False)
