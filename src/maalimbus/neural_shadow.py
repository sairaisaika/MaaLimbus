"""Read-only Maa neural inference. No torch, ONNX Runtime or device controller here."""
import hashlib
from pathlib import Path
from .storage import read_json
from .sinner_detection import LABELS,proposals


def measured_card_border(image,cell):
    """Search geometry never labels a sinner: require four actual visible strips."""
    import cv2,numpy as np
    x,y,w,h=cell;hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    colored=((hsv[:,:,0]>=12)&(hsv[:,:,0]<=43)&(hsv[:,:,1]>=80)&(hsv[:,:,2]>=25)).astype(np.float32)
    def vertical(center):
        options=[(float(colored[y+35:y+h-30,n:n+4].mean()),n) for n in range(center-14,center+15)]
        score,n=max(options);return n+2,score
    left,ls=vertical(x);right,rs=vertical(x+w)
    def horizontal(center):
        options=[(float(colored[n:n+4,left+20:right-25].mean()),n) for n in range(center-14,center+15)]
        score,n=max(options);return n+2,score
    top,ts=horizontal(y);bottom,bs=horizontal(y+h)
    if min(ls,rs,ts,bs)<.72 or not (165<=right-left<=210 and 245<=bottom-top<=300):return None
    return [left,top,right-left,bottom-top],dict(left=ls,right=rs,top=ts,bottom=bs)


def verified_card_rois(image,record):
    """Optional research ROI inference on independently named pre-battle pages.

    Header/buttons are native OCR; card sides are measured actual pixels. The
    fixed grid is only a search window, never a class or a claimed card boundary.
    """
    from .vision import Text,find
    if not record or record.get('scene')!='PRE_BATTLE_TEAM' or record.get('size')!=[1920,1080]:return []
    if list(image.shape[:2])!=[1080,1920]:return []
    records=[Text(x['text'],tuple(x['box']),x['score']) for x in record.get('ocr',[])]
    for label,roi in ((r'^(?:To\s*)?Battle!$',(.81,.74,.98,.91)),
                      (r'^Details$',(.60,.12,.80,.25))):
        if len(find(records,label,roi,record['size'],.9))!=1:return []
    rois=[]
    for n in range(12):
        border=measured_card_border(image,[350+(n%6)*198,225+(n//6)*298,185,273])
        if border is None:continue
        x,y,w,h=border[0]
        rois.append(dict(grid_slot=n,roi=[x-10,y-10,w+20,h+20],measured_boundary=border[0],
            border_scores=border[1],class_source='native_neural_only_not_grid_position'))
    return rois


def detection_metrics(data,rows,iou_threshold=.75,*,research_fit=False):
    """One-to-one held-out scoring. Missing/duplicate images or leaked episodes refuse.

    Precision .98, recall .95 and IoU .75 are explicit engineering promotion
    targets, not claimed game formulas. Both held-out partitions need negatives.
    """
    if not .5<=iou_threshold<=1:raise ValueError('Invalid IoU threshold')
    parts=('train',) if research_fit else ('validation','test')
    samples={s['image_sha256']:s for s in data['samples'] if s['split'] in parts}
    if not samples or len(samples)!=len(rows):raise ValueError('Every held-out image requires exactly one replay')
    seen=set();stats={p:{l:dict(tp=0,fp=0,fn=0,ious=[]) for l in LABELS}
                      for p in parts};negative={p:0 for p in stats}
    def iou(a,b):
        ax,ay,aw,ah=a;bx,by,bw,bh=b
        overlap=max(0,min(ax+aw,bx+bw)-max(ax,bx))*max(0,min(ay+ah,by+bh)-max(ay,by))
        return overlap/(aw*ah+bw*bh-overlap)
    for row in rows:
        sha=row.get('image_sha256');s=samples.get(sha)
        if s is None or sha in seen:raise ValueError('Unknown/duplicate held-out image')
        seen.add(sha)
        if any(row.get(k)!=s[k] for k in ('proof_sha256','episode','split')):
            raise ValueError('Held-out review or episode binding differs')
        detections=proposals(dict(size=s['size']),row['predictions'],threshold=.9)
        part=s['split'];negative[part]+=not s['boxes']
        for label in LABELS:
            truths=[b['box'] for b in s['boxes'] if b['label']==label]
            predictions=[d for d in detections if d['label']==label]
            unmatched=set(range(len(truths)));stat=stats[part][label]
            for d in sorted(predictions,key=lambda d:d['score'],reverse=True):
                options=[(iou(d['box'],truths[n]),n) for n in unmatched]
                score,n=max(options) if options else (0,None)
                if score>=iou_threshold:
                    unmatched.remove(n);stat['tp']+=1;stat['ious'].append(score)
                else:stat['fp']+=1
            stat['fn']+=len(unmatched)
    for classes in stats.values():
        for stat in classes.values():
            tp,fp,fn=stat['tp'],stat['fp'],stat['fn']
            stat.update(precision=tp/(tp+fp) if tp+fp else 0,
                recall=tp/(tp+fn) if tp+fn else 0,
                mean_iou=sum(stat['ious'])/len(stat['ious']) if stat['ious'] else 0)
            del stat['ious']
    passed=not research_fit and data.get('training_ready') is True and all(negative[p]>0 and all(s['precision']>=.98 and s['recall']>=.95 and
               s['mean_iou']>=iou_threshold for s in classes.values()) for p,classes in stats.items())
    return dict(schema_version=1,labels=list(LABELS),samples=rows,metrics=stats,
        negative_images=negative,iou_threshold=iou_threshold,quality_passed=passed,
        targets=dict(precision=.98,recall=.95,mean_iou=iou_threshold),
        validation_and_test_independent=not research_fit,research_fit_only=research_fit)


def verified_model(resource,policy):
    """Bind shadow to actual training/native-evaluation artifacts; never grant input."""
    resource=Path(resource)
    model=resource/'model/detect/sinners.onnx'
    card=resource/'model/detect/sinners.model-card.json'
    evaluation=resource/'model/detect/sinners.native-evaluation.json'
    for path in (model,card,evaluation):
        if path.is_symlink() or not path.is_file():raise ValueError('Audited ONNX model/card/evaluation absent')
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    metadata=read_json(card);native=read_json(evaluation);sha=digest(model)
    if (sha!=policy.get('model_sha256') or digest(card)!=policy.get('model_card_sha256') or
            digest(evaluation)!=metadata.get('native_evaluation_sha256') or
            policy.get('labels')!=list(LABELS) or metadata.get('labels')!=list(LABELS)):
        raise ValueError('Shadow model/card/classes hash differs')
    if (metadata.get('training_complete') is not True or metadata.get('synthetic_model') is not False or
            metadata.get('onnx_sha256')!=sha or native.get('model_sha256')!=sha or
            native.get('dataset_manifest_sha256')!=metadata.get('dataset_manifest_sha256') or
            any(native.get(k)!=metadata.get(k) for k in ('dataset_configuration_sha256','native_preprocessing_sha256')) or
            native.get('recognizer')!='MaaFramework.NeuralNetworkDetect' or
            native.get('input_sent') is not False or native.get('game_controller') is not False):
        raise ValueError('Actual trained native-held-out artifact binding required')
    if policy.get('production_enabled') or policy.get('input_authorized'):
        raise ValueError('Shadow cannot grant gameplay input')
    return sha,metadata,native


def observe(context,image,resource,*,record=None):
    resource=Path(resource)
    policy_file=resource/'neural-learning.local.json'
    if not policy_file.exists():policy_file=resource/'neural-learning.json'
    policy=read_json(policy_file)
    if policy.get('mode')=='off':return dict(status='off',model_trained=False,input_authorized=False)
    if policy.get('mode')!='shadow':raise ValueError('Only read-only neural shadow is supported')
    digest,metadata,native=verified_model(resource,policy)
    from maa.pipeline import JRecognitionType,JNeuralNetworkDetect
    roi_mode=policy.get('roi_mode','full_frame')
    if roi_mode not in ('full_frame','verified_card_edges'):raise ValueError('Unsupported neural search policy')
    rois=verified_card_rois(image,record) if roi_mode=='verified_card_edges' else [dict(roi=[0,0,image.shape[1],image.shape[0]])]
    detections=[]
    for candidate in rois:
        detail=context.run_recognition_direct(JRecognitionType.NeuralNetworkDetect,
            JNeuralNetworkDetect(model='sinners.onnx',labels=list(LABELS),expected=list(range(12)),
                threshold=[.9]*12,order_by='Score',roi=candidate['roi']),image)
        if detail is None:raise ValueError('Native neural result absent')
        if detail.hit:detections.extend(dict(class_index=r.cls_index,box=list(r.box),score=r.score)
                                       for r in detail.filtered_results)
    size_record=dict(size=[image.shape[1],image.shape[0]])
    return dict(status='shadow',model_sha256=digest,boxes=proposals(size_record,detections),
        policy_file=policy_file.name,
        roi_mode=roi_mode,verified_rois=rois,native_inference_executed=bool(rois),
        model_trained=True,native_quality_passed=native.get('quality_passed') is True,
        training_eligible=False,production_enabled=False,input_authorized=False)
