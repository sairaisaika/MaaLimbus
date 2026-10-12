"""Maa-native sinner box proposals; predictions are never training truth."""
import math
from .storage import SINNERS

LABELS=tuple(name.lower().replace(' ','_') for name in SINNERS)
GAME_NUMBERS=(1,2,3,4,5,6,7,8,9,11,12,13)


def box(value,size):
    if (not isinstance(value,(list,tuple)) or len(value)!=4 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in value)):
        raise ValueError('Finite xywh sinner box required')
    x,y,w,h=value
    if w<=0 or h<=0 or x<0 or y<0 or x+w>size[0] or y+h>size[1]:
        raise ValueError('Sinner box outside actual image')
    return list(value)


def proposals(record,detections,*,teacher='maa_neural_detect',threshold=.9):
    size=record.get('size')
    if (not isinstance(size,list) or len(size)!=2 or
            any(type(v) is not int or v<=0 for v in size)):
        raise ValueError('Actual image dimensions required')
    if not 0<=threshold<=1:raise ValueError('Invalid confidence threshold')
    rows=[]
    for d in detections:
        index=d.get('class_index');score=d.get('score')
        if type(index) is not int or not 0<=index<len(LABELS):
            raise ValueError('Unknown sinner detection class')
        if type(score) not in (int,float) or not math.isfinite(score) or not 0<=score<=1:
            raise ValueError('Invalid native detection confidence')
        if score<threshold:continue
        rows.append(dict(class_id=index,label=LABELS[index],sinner=SINNERS[index],
            game_number=GAME_NUMBERS[index],box=box(d.get('box'),size),score=score,
            teacher=teacher,reviewed=False,training_eligible=False))
    counts={i:sum(r['class_id']==i for r in rows) for i in range(12)}
    for row in rows:
        row['review_reason']='duplicate_identity' if counts[row['class_id']]>1 else 'identity_and_card_boundary_review_required'
    return rows


def native_pipeline(model='sinners.onnx'):
    if model!='sinners.onnx':raise ValueError('Use the audited sinner model name')
    return {f'SinnerDetect{i+1:02}':dict(enabled=False,recognition=dict(
        type='NeuralNetworkDetect',param=dict(model=model,labels=list(LABELS),
        expected=[i],threshold=.9,order_by='Score',index=0)),
        action=dict(type='DoNothing')) for i in range(12)}
