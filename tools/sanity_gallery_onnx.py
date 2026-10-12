"""Sanity: does the trained ONNX still classify its own training crops?"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
from maalimbus.learning_dataset import digest,local_file
from maalimbus.sinner_detection import LABELS
from compare_sinner_preprocessing import proposals,square,letterbox
import cv2,numpy as np
parser=argparse.ArgumentParser()
parser.add_argument('--model',type=Path,required=True)
parser.add_argument('--gallery',type=Path,required=True)
parser.add_argument('--limit',type=int,default=20)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
net=cv2.dnn.readNetFromONNX(str(args.model))
manifest=json.load(open(args.gallery,encoding='utf-8'))
rows=[];only_box=[]
for line in manifest['samples'][:args.limit]:
    path=local_file(ROOT,line['frame']);pixels=cv2.imread(str(path))
    box=line['boxes'][0]['box'];x,y,w,h=box
    patch=pixels[y:y+h,x:x+w]
    sq=proposals(net,square(patch));lb,_=letterbox(patch);lbr=proposals(net,lb)
    full_sq=proposals(net,square(pixels))
    rows.append(dict(frame=line['frame'],label=line['boxes'][0]['label'],box=box,
        square=LABELS[sq[0][1]] if sq else None,square_score=round(sq[0][0],4) if sq else None,
        letterbox=LABELS[lbr[0][1]] if lbr else None,letterbox_score=round(lbr[0][0],4) if lbr else None,
        full_crop_square=LABELS[full_sq[0][1]] if full_sq else None,
        full_crop_square_score=round(full_sq[0][0],4) if full_sq else None))
report=dict(model_sha256=digest(args.model),
    crop_definition=manifest['samples'][0]['boxes'][0]['box'],
    square_top1_correct=sum(1 for r in rows if r['square']==r['label']),
    letterbox_top1_correct=sum(1 for r in rows if r['letterbox']==r['label']),
    full_crop_square_top1_correct=sum(1 for r in rows if r['full_crop_square']==r['label']),
    samples=len(rows),rows=rows,held_out_accuracy_verified=False,production_enabled=False)
args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
