"""Replay a trained detector against reviewed held-out images using Maa, no device."""
import argparse,json,sys,tempfile,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.sinner_dataset import verify_export
from maalimbus.sinner_detection import LABELS
from maalimbus.learning_dataset import digest,local_file
from maalimbus.neural_shadow import detection_metrics
from maalimbus.storage import write_json

from maalimbus.replay import ReplayController

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--maafw',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--research',action='store_true')
    p.add_argument('--research-fit',action='store_true',help='Native training-frame replay; NOT held-out metrics')
    a=p.parse_args();data=verify_export(ROOT,a.dataset,research=a.research)
    if a.research_fit and not a.research:raise ValueError('Fit-only replay is research only')
    if a.model.is_symlink() or not a.model.is_file():raise ValueError('Local trained ONNX required')
    import cv2,numpy as np
    from maa.library import Library
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.controller import CustomController
    from maa.pipeline import JRecognitionType,JNeuralNetworkDetect
    from maalimbus.jobs import wait_job
    class Offline(ReplayController):
        def __init__(self):
            super().__init__(np.zeros((640,640,3),dtype=np.uint8))
    Library.open(a.maafw,agent_server=False);rows=[]
    with tempfile.TemporaryDirectory(prefix='maalimbus-heldout-') as directory:
        bundle=Path(directory);(bundle/'model/detect').mkdir(parents=True)
        shutil.copyfile(a.model,bundle/'model/detect/sinners.onnx')
        resource=Resource();wait_job(resource.post_bundle(bundle),timeout=30)
        controller=Offline();wait_job(controller.post_connection(),timeout=10)
        tasker=Tasker()
        if not tasker.bind(resource,controller):raise ValueError('Offline native binding failed')
        for sample in data['samples']:
            if sample['split'] not in (('train',) if a.research_fit else ('validation','test')):continue
            image=cv2.imread(str(local_file(ROOT,sample['frame'])))
            start=time.perf_counter()
            job=tasker.post_recognition(JRecognitionType.NeuralNetworkDetect,
                JNeuralNetworkDetect(model='sinners.onnx',labels=list(LABELS),
                    expected=list(range(12)),threshold=[.9]*12,order_by='Score'),image)
            wait_job(job,timeout=60);detail=job.get()
            if detail is None or not detail.nodes or detail.nodes[-1].recognition is None:
                raise ValueError('Native held-out result missing')
            reco=detail.nodes[-1].recognition
            predictions=[dict(class_index=r.cls_index,box=list(r.box),score=float(r.score))
                         for r in reco.filtered_results] if reco.hit else []
            rows.append(dict(image_sha256=sample['image_sha256'],proof_sha256=sample['proof_sha256'],
                episode=sample['episode'],split=sample['split'],predictions=predictions,
                latency_ms=(time.perf_counter()-start)*1000))
    report=detection_metrics(data,rows,research_fit=a.research_fit)
    report.update(model_sha256=digest(a.model),dataset_manifest_sha256=digest(a.dataset/'manifest.json'),
        dataset_configuration_sha256=digest(a.dataset/'data.yaml'),
        native_preprocessing_sha256=digest(a.dataset/'native-resize.json') if (a.dataset/'native-resize.json').exists() else None,
        recognizer='MaaFramework.NeuralNetworkDetect',threshold=.9,game_controller=False,
        input_sent=False,production_enabled=False)
    write_json(a.out,report)
    print(json.dumps(dict(output=str(a.out),native_quality_passed=report['quality_passed'],
                         production_enabled=False)))


if __name__=='__main__':main()
