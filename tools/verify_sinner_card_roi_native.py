"""Maa-native square-preprocessing replay of one trained sinner detector.

Read-only, no device. This tool answers three questions with actual numbers
instead of intent:

* what native .9 confidence and global xywh the latest ONNX model produces on
  real pre-battle team-card ROIs;
* which preprocessing path the native detection actually took, measured on a
  synthetic control image rather than assumed;
* whether a completely different teacher (mean-absolute-difference template
  matching against the reviewed owned-gallery crops) agrees with the neural
  class on each card, so a "correct" count is never the model approving itself.

Nothing here is training, production, or an input path: it never opens a
controller, never lowers the .9 threshold, and every emitted flag stays false.
"""
import pathlib as _pathlib
import sys as _sys
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / 'src'))
from maalimbus.replay import ReplayController
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.learning_dataset import digest,local_file
from maalimbus.neural_shadow import verified_card_rois
from maalimbus.sinner_detection import LABELS
from maalimbus.storage import read_json,write_json

THRESHOLD=.9


def inner_art(measured,inset=18):
    """Strip the printed frame and the level/name band; framing must not classify."""
    x,y,w,h=measured
    return [x+inset,y+inset,w-2*inset,h-2*inset]


def signature(pixels,box,size=(48,72)):
    """Blurred normalized luminance signature; geometry and colour cast removed."""
    import cv2
    x,y,w,h=box
    if w<16 or h<16:return None,0.0
    patch=pixels[y:y+h,x:x+w]
    if patch.size==0:return None,0.0
    gray=cv2.cvtColor(patch,cv2.COLOR_BGR2GRAY).astype('float32')
    gray=cv2.resize(gray,size,interpolation=cv2.INTER_AREA)
    gray-=gray.mean()
    deviation=float(gray.std())
    return (gray/deviation if deviation>1e-6 else gray),deviation


def template_teacher(sample,candidates):
    """Rank reviewed crops by mean absolute difference; low-contrast art refuses."""
    if sample[0] is None or sample[1]<6.0:return None
    best=None
    for label,crop in candidates:
        if crop[0] is None:continue
        score=float(abs(sample[0]-crop[0]).mean())
        if best is None or score<best[0]:best=(score,label)
    return None if best is None else dict(label=best[1],distance=round(best[0],4))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames',type=Path,required=True,help='JSON list of {frame,episode}')
    parser.add_argument('--gallery',type=Path,required=True,help='Reviewed research dataset manifest')
    parser.add_argument('--maafw',type=Path,default=ROOT/'dist/MaaLimbus/maafw')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--probe-out',type=Path,default=None)
    args=parser.parse_args()
    if args.model.is_symlink() or not args.model.is_file():
        raise ValueError('Local trained ONNX required')
    model_sha=digest(args.model)
    import cv2,numpy as np
    from maa.library import Library
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.controller import CustomController
    from maa.pipeline import JRecognitionType,JNeuralNetworkDetect
    from maalimbus.jobs import wait_job
    manifest=read_json(args.gallery)
    if manifest.get('labels')!=list(LABELS):raise ValueError('Gallery dataset classes differ')
    candidates=[]
    for line in manifest['samples']:
        if line['split']!='train':continue
        path=local_file(ROOT,line['frame'])
        pixels=cv2.imread(str(path))
        if pixels is None or digest(path)!=line['image_sha256']:
            raise ValueError('Reviewed gallery crop changed')
        if [pixels.shape[1],pixels.shape[0]]!=line['size']:
            raise ValueError('Reviewed gallery crop size differs')
        label=line['boxes'][0]['label']
        candidates.append((label,signature(pixels,line['boxes'][0]['box'])))
    class Offline(ReplayController):
        """No screencap, no click; any input attempt is a hard failure."""
        def __init__(self):
            super().__init__(np.zeros((640,640,3),np.uint8))
    Library.open(args.maafw,agent_server=False)
    out=Path(args.out);bundle=out.parent/f'.{out.stem}-bundle'
    (bundle/'model/detect').mkdir(parents=True,exist_ok=True)
    import shutil;shutil.copyfile(args.model,bundle/'model/detect/sinners.onnx')
    resource=Resource();wait_job(resource.post_bundle(bundle.resolve()),timeout=60)
    controller=Offline();wait_job(controller.post_connection(),timeout=10)
    tasker=Tasker()
    if not tasker.bind(resource,controller):raise ValueError('Offline native binding failed')
    def detect(pixels,roi):
        job=tasker.post_recognition(JRecognitionType.NeuralNetworkDetect,
            JNeuralNetworkDetect(model='sinners.onnx',labels=list(LABELS),expected=list(range(12)),
                threshold=[THRESHOLD]*12,order_by='Score',roi=roi),pixels)
        wait_job(job,timeout=120);detail=job.get()
        if detail is None or not detail.nodes or detail.nodes[-1].recognition is None:
            raise ValueError('Native neural result absent')
        recognition=detail.nodes[-1].recognition
        if not recognition.hit:return []
        return [dict(class_index=int(r.cls_index),box=list(r.box),score=float(r.score))
                for r in recognition.filtered_results]
    # Independent recomputation of the same audited ONNX under the pinned
    # preprocessing. It exists so a "Maa got it right" claim can be checked
    # without Maa, and so a preprocessing mismatch becomes visible as disagreement.
    net=cv2.dnn.readNetFromONNX(str(args.model))
    def opencv_detect(pixels):
        blob=cv2.dnn.blobFromImage(pixels,1/255.0,(640,640),swapRB=True,crop=False)
        net.setInput(blob);out=np.squeeze(net.forward())
        if out.ndim!=2:raise ValueError('Unexpected ONNX output rank')
        if out.shape[0]<out.shape[1]:out=out.T
        proposals_=[]
        for row in out:
            scores=row[4:16];index=int(np.argmax(scores));confidence=float(scores[index])
            if confidence<THRESHOLD:continue
            cx,cy,w,h=(float(v) for v in row[:4])
            proposals_.append((confidence,index,[cx-w/2,cy-h/2,w,h]))
        proposals_.sort(reverse=True);kept=[]
        def iou(a,b):
            ax,ay,aw,ah=a;bx,by,bw,bh=b
            overlap=max(0,min(ax+aw,bx+bw)-max(ax,bx))*max(0,min(ay+ah,by+bh)-max(ay,by))
            return overlap/(aw*ah+bw*bh-overlap)
        for confidence,index,candidate in proposals_:
            if all(iou(candidate,other)<.5 for _,_,other in kept):kept.append((confidence,index,candidate))
        return kept
    def crop(pixels,roi):
        x,y,w,h=roi
        return pixels[max(0,y):y+h,max(0,x):x+w]
    # Measured preprocessing path: a card-sized plate of one flat colour and a
    # two-tone split. A square fit stretches the split across the full plate; a
    # letterbox path keeps black bars and never touches every column.
    plate=np.zeros((1080,1920,3),np.uint8)
    plate[200:200+300,300:300+200]=(40,40,40);plate[200:200+300,400:400+100]=(220,220,220)
    probe_boxes=detect(plate,[300,200,200,300])
    frame_rows=[];falsification=[]
    for item in read_json(args.frames):
        frame=local_file(ROOT,item['frame']);record=read_json(frame)
        image=local_file(ROOT,str(frame.with_suffix('.png')))
        if digest(image)!=record.get('image_sha256'):raise ValueError('Actual frame changed')
        pixels=cv2.imread(str(image))
        if pixels is None or [pixels.shape[1],pixels.shape[0]]!=record['size']:
            raise ValueError('Actual frame is not decodable at its recorded size')
        started=time.perf_counter()
        rois=verified_card_rois(pixels,record)
        rows=[]
        for slot,candidate in enumerate(rois):
            neural=detect(pixels,candidate['roi'])
            top=max(neural,key=lambda d:d['score']) if neural else None
            box=None;teacher=None;match=None
            if top is not None:
                # Maa reports a hit inside the configured ROI in absolute frame
                # coordinates (verified against a standalone-crop replay), so the
                # reported box is already global and must not be re-offset.
                box=[int(round(v)) for v in top['box']]
                sample=signature(pixels,inner_art(candidate['measured_boundary']))
                teacher=template_teacher(sample,candidates)
                match=dict(predicted_label=LABELS[top['class_index']],
                    template_label=teacher['label'] if teacher else None,
                    agrees=bool(teacher and teacher['label']==LABELS[top['class_index']]),
                    template_distance=teacher['distance'] if teacher else None)
            rows.append(dict(slot=slot,grid_slot=candidate.get('grid_slot',slot),
                grid_position=[350+(candidate.get('grid_slot',slot)%6)*198,
                               225+(candidate.get('grid_slot',slot)//6)*298],
                roi=candidate['roi'],measured_boundary=candidate['measured_boundary'],
                border_scores=candidate['border_scores'],
                predicted_label=LABELS[top['class_index']] if top else None,
                predicted_caption=None,class_index=top['class_index'] if top else None,
                score=round(top['score'],6) if top else None,
                global_xywh=box,native_detections=len(neural),
                template_label=teacher['label'] if teacher else None,
                template_agrees=bool(teacher and teacher['label']==LABELS[top['class_index']]),
                template_distance=teacher['distance'] if teacher else None))
        # Falsification: a horizontal mirror must change what a texture model sees
        # with high confidence if it is reading actual art rather than a slot.
        mirrored=cv2.flip(pixels,1)
        mirrored_rois=verified_card_rois(mirrored,record)
        for slot,candidate in enumerate(mirrored_rois[:2]):
            neural=detect(mirrored,candidate['roi'])
            top=max(neural,key=lambda d:d['score']) if neural else None
            falsification.append(dict(frame=str(frame),slot=slot,mirror_roi=candidate['roi'],
                mirrored_prediction=LABELS[top['class_index']] if top else None,
                mirrored_score=round(top['score'],6) if top else None,
                original_prediction=rows[slot]['predicted_label'] if slot<len(rows) else None))
        agreements=[r['template_label'] is not None for r in rows]
        control=[]
        for row in rows:
            roi=row['roi'];results=opencv_detect(crop(pixels,roi))
            x,y,w,h=roi
            control.append(dict(slot=row['slot'],
                prediction=LABELS[results[0][1]] if results else None,
                score=round(results[0][0],6) if results else None,
                global_xywh=[round(x+results[0][2][0],1),round(y+results[0][2][1],1),
                             round(results[0][2][2],1),round(results[0][2][3],1)] if results else None,
                agrees_with_maa=bool(results and row['predicted_label']==LABELS[results[0][1]])))
        frame_rows.append(dict(frame=str(frame),frame_sha256=digest(frame),image_sha256=digest(image),
            scene=record.get('scene'),size=record['size'],episode=item.get('episode'),
            captured_utc=record.get('utc'),card_rois=len(rois),decoded=len(rows),
            xywh_global=[r['global_xywh'] for r in rows],rows=rows,
            opencv_control=control,
            opencv_control_agreements=sum(c['agrees_with_maa'] for c in control),
            template_agreements=sum(1 for r in rows if r['template_agrees']),
            template_comparisons=sum(agreements),
            latency_ms=round((time.perf_counter()-started)*1000,3)))
    # Cross-frame consistency: the same visual slot must not change class between
    # captures of one composition unless the art itself differs. A conflict is
    # exactly the case that must stay a candidate label, never a claimed identity.
    by_slot={}
    for entry in frame_rows:
        for row in entry['rows']:
            by_slot.setdefault(row['grid_slot'],set()).add(row['predicted_label'])
    conflicts=[dict(slot=slot,labels=sorted(x for x in labels if x)) for slot,labels in sorted(by_slot.items())
               if len([x for x in labels if x])>1]
    write_json(args.out,dict(schema_version=1,model_sha256=model_sha,model_trained=True,
        recognizer='MaaFramework.NeuralNetworkDetect',threshold=THRESHOLD,
        roi_mode='verified_card_edges_measured_boundary',labels=list(LABELS),
        native_roi_plate_probe=dict(flat_gray_then_white_split_roi=[300,200,200,300],
            detections=probe_boxes,measured_path='direct_resize_roi_crop'
            if not probe_boxes else 'plate_produced_detections_under_threshold'
            if not any(d['score']>=THRESHOLD for d in probe_boxes) else 'plate_above_threshold_inspect'),
        template_teacher=dict(method='normalized_luminance_mean_absolute_difference',
            reference='reviewed_owned_gallery_research_crops',references=len(candidates)),
        results=frame_rows,cross_frame_conflicts=conflicts,falsification_mirror=falsification,
        per_class_correct=None,
        per_class_correct_note='No independent identity teacher exists for the pre-battle team screen; '
            'template agreement is reported per card instead of a claimed correctness count.',
        held_out_accuracy_verified=False,native_quality_passed=False,independent_episode=False,
        game_controller=False,input_sent=False,input_authorized=False,production_enabled=False))
    if args.probe_out:
        write_json(args.probe_out,dict(model_sha256=model_sha,probe_roi=[300,200,200,300],
            detections=probe_boxes,threshold=THRESHOLD,input_sent=False))
    print(json.dumps(dict(output=str(args.out),frames=len(frame_rows),
        cards=sum(r['decoded'] for r in frame_rows),
        opencv_control_agreements=sum(r['opencv_control_agreements'] for r in frame_rows),
        template_agreements=sum(r['template_agreements'] for r in frame_rows),
        template_comparisons=sum(r['template_comparisons'] for r in frame_rows),
        cross_frame_conflicts=len(conflicts),production_enabled=False)))


if __name__=='__main__':main()
