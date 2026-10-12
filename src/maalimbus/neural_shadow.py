"""Read-only Maa neural inference. No torch, ONNX Runtime or device controller here."""
import hashlib
from pathlib import Path
from .storage import read_json
from .sinner_detection import LABELS,proposals


def observe(context,image,resource):
    resource=Path(resource);policy=read_json(resource/'neural-learning.json')
    if policy.get('mode')=='off':return dict(status='off',model_trained=False,input_authorized=False)
    if policy.get('mode')!='shadow':raise ValueError('Only read-only neural shadow is supported')
    model=resource/'model/detect/sinners.onnx'
    if model.is_symlink() or not model.is_file():raise ValueError('Audited ONNX model absent')
    digest=hashlib.sha256(model.read_bytes()).hexdigest()
    if digest!=policy.get('model_sha256') or policy.get('labels')!=list(LABELS):
        raise ValueError('Shadow model hash or classes differ')
    from maa.pipeline import JRecognitionType,JNeuralNetworkDetect
    detail=context.run_recognition_direct(JRecognitionType.NeuralNetworkDetect,
        JNeuralNetworkDetect(model='sinners.onnx',labels=list(LABELS),expected=list(range(12)),
                             threshold=[.9]*12,order_by='Score'),image)
    if detail is None:raise ValueError('Native neural result absent')
    detections=[dict(class_index=r.cls_index,box=list(r.box),score=r.score)
                for r in detail.filtered_results] if detail.hit else []
    record=dict(size=[image.shape[1],image.shape[0]])
    return dict(status='shadow',model_sha256=digest,boxes=proposals(record,detections),
        training_eligible=False,production_enabled=False,input_authorized=False)
