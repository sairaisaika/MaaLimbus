"""Maa-native trained-shadow replay on real full game frames, no physical controller."""
import pathlib as _pathlib
import sys as _sys
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / 'src'))
import argparse,sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.learning_dataset import digest,local_file
from maalimbus.neural_shadow import verified_model,verified_card_rois
from maalimbus.sinner_detection import LABELS,proposals

from maalimbus.replay import ReplayController

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--resource',type=Path,required=True);p.add_argument('--frames',type=Path,required=True)
    p.add_argument('--maafw',type=Path,default=ROOT/'dist/MaaLimbus/maafw');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--verified-card-rois',action='store_true')
    a=p.parse_args();policy=read_json(a.resource/'neural-learning.json');sha,card,native=verified_model(a.resource,policy)
    import cv2,numpy as np
    from maa.library import Library
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.controller import CustomController
    from maa.pipeline import JRecognitionType,JNeuralNetworkDetect
    from maalimbus.jobs import wait_job
    class Offline(ReplayController):
        def __init__(self):
            super().__init__(np.zeros((640,640,3),np.uint8))
    Library.open(a.maafw,agent_server=False);resource=Resource()
    wait_job(resource.post_bundle(a.resource.resolve()),timeout=30)
    controller=Offline();wait_job(controller.post_connection(),timeout=10);tasker=Tasker()
    if not tasker.bind(resource,controller):raise ValueError('Offline native binding failed')
    results=[]
    for item in read_json(a.frames):
        frame=local_file(ROOT,item['frame']);record=read_json(frame);image=local_file(ROOT,str(frame.with_suffix('.png')))
        if digest(image)!=record.get('image_sha256'):raise ValueError('Actual full frame changed')
        pixels=cv2.imread(str(image));start=time.perf_counter()
        rois=verified_card_rois(pixels,record) if a.verified_card_rois else [dict(roi=[0,0,pixels.shape[1],pixels.shape[0]])]
        detections=[]
        for candidate in rois:
            job=tasker.post_recognition(JRecognitionType.NeuralNetworkDetect,
                JNeuralNetworkDetect(model='sinners.onnx',labels=list(LABELS),expected=list(range(12)),
                    threshold=[.9]*12,order_by='Score',roi=candidate['roi']),pixels)
            wait_job(job,timeout=60);detail=job.get()
            if detail is None or not detail.nodes or detail.nodes[-1].recognition is None:
                raise ValueError('Native full-frame inference absent')
            reco=detail.nodes[-1].recognition
            if reco.hit:detections.extend(dict(class_index=r.cls_index,box=list(r.box),score=float(r.score))
                                        for r in reco.filtered_results)
        boxes=proposals(record,detections)
        results.append(dict(frame=str(frame),frame_sha256=digest(frame),image_sha256=digest(image),
            scene=record.get('scene'),episode=item.get('episode'),boxes=boxes,verified_rois=rois,
            latency_ms=(time.perf_counter()-start)*1000))
    write_json(a.out,dict(model_sha256=sha,model_trained=True,native_full_frame_replay=True,
        results=results,held_out_accuracy_verified=False,native_quality_passed=native['quality_passed'],
        game_controller=False,input_sent=False,production_enabled=False))
    print(json.dumps(dict(frames=len(results),boxes=sum(len(r['boxes']) for r in results),
        model_trained=True,held_out_accuracy_verified=False,production_enabled=False)))


if __name__=='__main__':main()
