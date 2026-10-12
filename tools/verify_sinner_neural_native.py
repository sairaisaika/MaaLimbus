"""Test Maa's ONNX protocol with a synthetic constant model, never a trained sinner model."""
import hashlib,json,sys,tempfile
from pathlib import Path
import numpy as np,onnx
from onnx import helper,numpy_helper,TensorProto
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.controller import CustomController
from maa.pipeline import JRecognitionType,JNeuralNetworkDetect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.jobs import wait_job
from maalimbus.storage import write_json
from maalimbus.sinner_detection import LABELS


class Offline(CustomController):
    def connect(self):return True
    def request_uuid(self):return 'synthetic-sinner-protocol-no-device'
    def get_features(self):return 0
    def screencap(self):return np.zeros((640,640,3),dtype=np.uint8)
    def click(self,*args):raise AssertionError('No input allowed')
    def touch_down(self,*args):raise AssertionError('No input allowed')
    def touch_up(self,*args):raise AssertionError('No input allowed')


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    with tempfile.TemporaryDirectory(prefix='maalimbus-synthetic-nn-') as directory:
        root=Path(directory);(root/'model/detect').mkdir(parents=True)
        raw=np.zeros((1,16,1),dtype=np.float32);raw[0,:4,0]=[320,320,100,100];raw[0,4+9,0]=.99
        graph=helper.make_graph([helper.make_node('Constant',[],['output'],value=numpy_helper.from_array(raw))],
            'synthetic_protocol_only',[helper.make_tensor_value_info('images',TensorProto.FLOAT,[1,3,640,640])],
            [helper.make_tensor_value_info('output',TensorProto.FLOAT,[1,16,1])])
        model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',17)]);model.ir_version=9
        onnx.checker.check_model(model);path=root/'model/detect/sinners.onnx';onnx.save(model,path)
        resource=Resource();wait_job(resource.post_bundle(root),timeout=30)
        controller=Offline();wait_job(controller.post_connection(),timeout=10)
        tasker=Tasker();assert tasker.bind(resource,controller)
        results=[]
        for expected,hit in ([9],True),([0],False),(list(range(12)),True):
            job=tasker.post_recognition(JRecognitionType.NeuralNetworkDetect,
                JNeuralNetworkDetect(model='sinners.onnx',labels=list(LABELS),expected=expected,threshold=[.9]*len(expected)),
                np.zeros((640,640,3),dtype=np.uint8))
            wait_job(job,timeout=30);detail=job.get()
            reco=detail.nodes[-1].recognition
            assert reco is not None and bool(reco.hit)==hit
            if hit:assert reco.best_result.cls_index==9 and list(reco.box)==[270,270,100,100]
            results.append(dict(expected=expected,hit=bool(reco.hit),box=list(reco.box) if reco.hit else None))
        write_json(ROOT/'build/sinner-neural-native-protocol-verification.json',dict(passed=True,
            results=results,fixture_model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            synthetic_model=True,model_trained=False,sinner_accuracy_verified=False,
            game_controller=False,input_sent=False,production_enabled=False))
        print(json.dumps(results))


if __name__=='__main__':main()
