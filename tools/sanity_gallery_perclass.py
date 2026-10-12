"""Full-gallery ONNX check: per-class top-1 on the only 130 research crops."""
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
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--insets',type=str,default='0,18')
args=parser.parse_args()
net=cv2.dnn.readNetFromONNX(str(args.model))
manifest=json.load(open(args.gallery,encoding='utf-8'))
insets=[int(v) for v in args.insets.split(',')]
mode={}
for inset in insets:
    rows=[];matrix={l:{} for l in LABELS}
    for line in manifest['samples']:
        path=local_file(ROOT,line['frame']);pixels=cv2.imread(str(path))
        x,y,w,h=line['boxes'][0]['box'];label=line['boxes'][0]['label']
        if inset:
            x+=inset;y+=inset;w-=2*inset;h-=2*inset
        if w<32 or h<32:continue
        patch=pixels[y:y+h,x:x+w]
        sq=proposals(net,square(patch))
        predicted=LABELS[sq[0][1]] if sq else None
        matrix[label][predicted]=matrix[label].get(predicted,0)+1
        rows.append(dict(frame=line['frame'],label=label,predicted=predicted,
            score=round(sq[0][0],4) if sq else None,box=[x,y,w,h]))
    mode[f'inset_{inset}']=dict(rows=rows,matrix=matrix,
        top1_correct=sum(1 for r in rows if r['predicted']==r['label']),samples=len(rows))
    per_class={}
    for label in LABELS:
        total=sum(matrix[label].values());correct=matrix[label].get(label,0)
        per_class[label]=dict(samples=total,correct=correct,
            correct_rate=round(correct/total,4) if total else None,
            confusions={k:v for k,v in sorted(matrix[label].items(),key=lambda kv:-kv[1]) if k!=label})
    mode[f'inset_{inset}']['per_class']=per_class
report=dict(model_sha256=digest(args.model),gallery=digest(args.gallery),
    gallery_samples=len(manifest['samples']),crop_box=manifest['samples'][0]['boxes'][0]['box'],
    modes=mode,note='This gallery is the training set of the same single episode; a score here is '
         'memorisation/research-fit, never held-out accuracy.',
    held_out_accuracy_verified=False,production_enabled=False)
args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
for key,value in mode.items():
    print(key,'top1',value['top1_correct'],'/',value['samples'])
    for label in LABELS:
        stats=value['per_class'][label]
        print(f"   {label:<12} {stats['correct']}/{stats['samples']} {stats['confusions']}")
