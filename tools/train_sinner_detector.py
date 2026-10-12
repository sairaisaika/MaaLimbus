"""Official Maa YOLO11 offline recipe. Requires a complete reviewed dataset."""
import argparse,json,sys,platform,importlib.metadata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.sinner_dataset import verify_export
from maalimbus.learning_dataset import digest
from maalimbus.storage import read_json,write_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True);p.add_argument('--weights',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--epochs',type=int,default=100)
    p.add_argument('--device',default='cpu');p.add_argument('--execute',action='store_true')
    p.add_argument('--research',action='store_true',help='Train incomplete reviewed data; cannot claim production quality')
    a=p.parse_args();a.dataset=a.dataset.resolve();a.weights=a.weights.resolve();a.out=a.out.resolve()
    data=verify_export(ROOT,a.dataset,research=a.research)
    if not 1<=a.epochs<=1000 or not a.weights.is_file():raise ValueError('Local YOLO11 checkpoint and bounded epochs required')
    if a.out.exists():raise ValueError('Training output must be a new directory')
    plan=dict(recipe='MaaNeuralNetworkCookbook/NeuralNetworkDetect',weights_sha256=digest(a.weights),
        dataset_manifest_sha256=digest(a.dataset/'manifest.json'),epochs=a.epochs,imgsz=640,seed=0,
        dataset_configuration_sha256=digest(a.dataset/'data.yaml'),
        native_preprocessing_sha256=digest(a.dataset/'native-resize.json') if (a.dataset/'native-resize.json').exists() else None,
        onnx_opset=17,nms=False,device=a.device,model_trained=False,production_enabled=False,
        labels=data['labels'],episodes=data['episodes'],python_version=platform.python_version(),
        research_only=a.research,
        native_replay_verified=False,held_out_metrics_verified=False)
    a.out.mkdir(parents=True)
    write_json(a.out/'training-plan.json',plan)
    if a.execute:
        from ultralytics import YOLO
        plan['ultralytics_version']=importlib.metadata.version('ultralytics')
        plan['torch_version']=importlib.metadata.version('torch')
        model=YOLO(str(a.weights))
        training_data=a.dataset/'data.yaml'
        if a.research and not any(s['split']=='validation' for s in data['samples']):
            fit=read_json(training_data);fit['val']=fit['train']
            training_data=a.out/'fit-data.yaml';write_json(training_data,fit)
            plan['fit_validation_uses_training_images']=True
            # This optimizer diagnostic is expressly NOT a held-out evaluation.
        model.train(data=str(training_data),epochs=a.epochs,imgsz=640,seed=0,device=a.device,
                    project=str(a.out),name='train',exist_ok=False,deterministic=True,workers=0,
                    val=not plan.get('fit_validation_uses_training_images',False),batch=8,amp=False)
        # Ultralytics writes label caches alongside inputs; retain them outside
        # the immutable reviewed export before its next evidence verification.
        for cache in (a.dataset/'labels').glob('*.cache'):
            retained=a.out/(cache.name+'.training-cache')
            cache.replace(retained)
        trained=YOLO(str(a.out/'train/weights/best.pt'))
        path=Path(trained.export(format='onnx',opset=17,imgsz=640,dynamic=False,nms=False,simplify=False))
        # Metrics use the exported ONNX artifact, not only its training checkpoint.
        detector=YOLO(str(path),task='detect');metrics={}
        for part in ('val','test'):
            partition='validation' if part=='val' else 'test'
            if not any(s['split']==partition for s in data['samples']):
                metrics[part]=None;continue
            result=detector.val(data=str(a.dataset/'data.yaml'),split=part,imgsz=640,
                device=a.device,conf=.9,project=str(a.out),name='onnx-'+part,exist_ok=False)
            metrics[part]={key:float(value) for key,value in result.results_dict.items()}
        plan.update(model_trained=True,onnx=str(path),onnx_sha256=digest(path),
                    checkpoint_sha256=digest(a.out/'train/weights/best.pt'),
                    exported_onnx_metrics=metrics,training_complete=True,synthetic_model=False)
    write_json(a.out/'training-plan.json',plan)
    print(json.dumps(plan))


if __name__=='__main__':main()
