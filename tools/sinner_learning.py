"""Offline proposal queue, reviewed YOLO dataset and Mirror progression reports."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import write_json,read_json
from maalimbus.learning_dataset import local_file,digest
from maalimbus.sinner_detection import proposals,native_pipeline
from maalimbus.sinner_dataset import manifest,export
from maalimbus.mirror_assessment import assess


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('propose');p.add_argument('--frame',required=True);p.add_argument('--detections',required=True);p.add_argument('--episode',required=True);p.add_argument('--locale',choices=['en','jp'],required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('dataset');p.add_argument('--annotations',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--export',type=Path)
    p=sub.add_parser('pipeline');p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('score');p.add_argument('--ledger',required=True);p.add_argument('--proof',required=True);p.add_argument('--out',type=Path,required=True)
    a=parser.parse_args()
    if a.command=='pipeline':result=native_pipeline()
    elif a.command=='score':result=assess(ROOT,a.ledger,a.proof)
    elif a.command=='dataset':
        result=manifest(ROOT,read_json(a.annotations))
        if a.export:export(ROOT,result,a.export)
    else:
        frame=local_file(ROOT,a.frame);record=read_json(frame);image=local_file(ROOT,str(frame.with_suffix('.png')))
        if digest(image)!=record.get('image_sha256'):raise ValueError('Actual frame binding differs')
        result=dict(version=1,episode=a.episode,locale=a.locale,frame=str(image.relative_to(ROOT)),
            image_sha256=digest(image),record_sha256=digest(frame),
            boxes=proposals(record,read_json(local_file(ROOT,a.detections))),
            reviewed=False,complete=False,training_eligible=False,input_authorized=False)
    write_json(a.out,result)
    print(json.dumps(dict(command=a.command,output=str(a.out),device_controller=False,input_sent=False)))


if __name__=='__main__':main()
