"""Prepare reviewed, verifier-bound real frames; no model, controller or input."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.learning_dataset import manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annotations',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=ROOT/'build/learning-reviewed-manifest.json')
    args=parser.parse_args()
    result=manifest(ROOT,json.loads(args.annotations.read_text(encoding='utf-8')))
    args.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(samples=len(result['samples']),episodes=len(result['episodes']),
        training_ready=result['training_ready'],model_trained=False,device_input=False)))
