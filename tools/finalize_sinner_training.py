"""Finalize a completed Ultralytics run without retraining (checks actual epoch log)."""
import argparse,csv,json,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.sinner_dataset import verify_export
from maalimbus.learning_dataset import digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--dataset',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();plan=read_json(a.plan);run=a.run.resolve();dataset=a.dataset.resolve();out=a.out.resolve()
    if out.exists():raise ValueError('New finalization output required')
    rows=list(csv.DictReader((run/'results.csv').read_text().splitlines()))
    if not rows or int(rows[-1]['epoch'])!=plan['epochs'] or len(rows)!=plan['epochs']:
        raise ValueError('Completed bounded epoch history required; do not finalize active runs')
    from ultralytics.utils import YAML
    args=YAML.load(run/'args.yaml')
    if args.get('epochs')!=plan['epochs'] or args.get('seed')!=plan['seed'] or args.get('deterministic') is not True:
        raise ValueError('Actual training arguments differ from plan')
    out.mkdir(parents=True)
    for cache in (dataset/'labels').glob('*.cache'):cache.replace(out/(cache.name+'.training-cache'))
    data=verify_export(ROOT,dataset,research=plan.get('research_only') is True)
    if digest(dataset/'manifest.json')!=plan['dataset_manifest_sha256'] or data['labels']!=plan['labels']:
        raise ValueError('Original reviewed training data differs')
    import shutil
    checkpoint=out/'best.pt';shutil.copyfile(run/'weights/best.pt',checkpoint)
    os.environ['YOLO_AUTOINSTALL']='false'
    from ultralytics import YOLO
    import importlib.metadata
    model=YOLO(str(checkpoint));onnx=Path(model.export(format='onnx',opset=17,
        imgsz=640,dynamic=False,nms=False,simplify=False))
    plan.update(onnx=str(onnx),onnx_sha256=digest(onnx),checkpoint_sha256=digest(checkpoint),
        model_trained=True,training_complete=True,synthetic_model=False,
        actual_training_run=str(run),completed_epochs=len(rows),
        ultralytics_version=importlib.metadata.version('ultralytics'),
        torch_version=importlib.metadata.version('torch'),
        fit_validation_uses_training_images=args.get('val') is False,
        training_results_sha256=digest(run/'results.csv'),actual_args_sha256=digest(run/'args.yaml'),
        exported_onnx_metrics=dict(val=None,test=None),native_replay_verified=False,
        held_out_metrics_verified=False,production_enabled=False)
    write_json(out/'training-plan.json',plan)
    print(json.dumps(dict(model_trained=True,onnx=str(onnx),onnx_sha256=plan['onnx_sha256'],
        held_out_metrics_verified=False,production_enabled=False)))


if __name__=='__main__':main()
