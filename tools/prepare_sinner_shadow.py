"""Prepare a NEW isolated Maa resource from actual training and native evaluation."""
import argparse,sys,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.learning_dataset import digest
from maalimbus.sinner_detection import LABELS
from maalimbus.neural_shadow import verified_model


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--training',type=Path,required=True)
    p.add_argument('--evaluation',type=Path,required=True)
    p.add_argument('--dataset',type=Path,help='Reverify exact training bytes and explicit native preprocessing')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--roi-mode',choices=['full_frame','verified_card_edges'],default='full_frame')
    a=p.parse_args();card=read_json(a.training);native=read_json(a.evaluation)
    if a.dataset:
        from maalimbus.sinner_dataset import verify_export
        verify_export(ROOT,a.dataset,research=card.get('research_only') is True)
        if digest(a.dataset/'manifest.json')!=card.get('dataset_manifest_sha256'):
            raise ValueError('Actual reviewed dataset differs')
        card.update(dataset_configuration_sha256=digest(a.dataset/'data.yaml'),
            native_preprocessing_sha256=digest(a.dataset/'native-resize.json') if (a.dataset/'native-resize.json').exists() else None)
        if any(card.get(k)!=native.get(k) for k in ('dataset_configuration_sha256','native_preprocessing_sha256')):
            raise ValueError('Actual native preprocessing evidence differs')
    model=Path(card.get('onnx',''))
    if (card.get('training_complete') is not True or card.get('synthetic_model') is not False or
            card.get('model_trained') is not True or card.get('labels')!=list(LABELS) or
            not model.is_file() or digest(model)!=card.get('onnx_sha256')):
        raise ValueError('Successful real training artifact required')
    if (native.get('model_sha256')!=card['onnx_sha256'] or
            native.get('dataset_manifest_sha256')!=card.get('dataset_manifest_sha256') or
            native.get('recognizer')!='MaaFramework.NeuralNetworkDetect' or
            native.get('input_sent') is not False or native.get('game_controller') is not False):
        raise ValueError('Matching no-device native held-out replay required')
    if a.out.exists():raise ValueError('Resource destination must be NEW; never replace installed assets')
    target=a.out/'model/detect';target.mkdir(parents=True)
    shutil.copyfile(model,target/'sinners.onnx')
    shutil.copyfile(a.evaluation,target/'sinners.native-evaluation.json')
    card.update(native_evaluation_sha256=digest(a.evaluation),
        native_replay_verified=True,native_quality_passed=native.get('quality_passed') is True,
        production_enabled=False,input_authorized=False)
    write_json(target/'sinners.model-card.json',card)
    policy=dict(version=2,mode='shadow',labels=list(LABELS),model_trained=True,
        roi_mode=a.roi_mode,
        model_sha256=digest(target/'sinners.onnx'),model_card_sha256=digest(target/'sinners.model-card.json'),
        production_enabled=False,input_authorized=False)
    write_json(a.out/'neural-learning.json',policy);verified_model(a.out,policy)
    print(json.dumps(dict(resource=str(a.out),model_trained=True,
        native_quality_passed=card['native_quality_passed'],production_enabled=False)))


if __name__=='__main__':main()
