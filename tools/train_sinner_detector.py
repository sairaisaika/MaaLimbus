"""Official Maa YOLO11 offline recipe. Requires a complete reviewed dataset."""
import argparse,json,sys
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
    a=p.parse_args();data=verify_export(ROOT,a.dataset)
    if not 1<=a.epochs<=1000 or not a.weights.is_file():raise ValueError('Local YOLO11 checkpoint and bounded epochs required')
    plan=dict(recipe='MaaNeuralNetworkCookbook/NeuralNetworkDetect',weights_sha256=digest(a.weights),
        dataset_manifest_sha256=digest(a.dataset/'manifest.json'),epochs=a.epochs,imgsz=640,seed=0,
        onnx_opset=17,nms=False,device=a.device,model_trained=False,production_enabled=False)
    if a.execute:
        from ultralytics import YOLO
        model=YOLO(str(a.weights))
        model.train(data=str(a.dataset/'data.yaml'),epochs=a.epochs,imgsz=640,seed=0,device=a.device,
                    project=str(a.out),name='train',exist_ok=False)
        trained=YOLO(str(a.out/'train/weights/best.pt'))
        path=Path(trained.export(format='onnx',opset=17,imgsz=640,dynamic=False,nms=False))
        plan.update(model_trained=True,onnx=str(path),onnx_sha256=digest(path),
                    native_replay_verified=False,held_out_metrics_verified=False)
    write_json(a.out/'training-plan.json',plan)
    print(json.dumps(plan))


if __name__=='__main__':main()
