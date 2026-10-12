"""Compare square-stretch vs Maa's own input path on the same real card crop."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.learning_dataset import digest,local_file
from maalimbus.sinner_detection import LABELS
from maalimbus.neural_shadow import verified_card_rois
import cv2,numpy as np
THRESHOLD=.9


def nms(rows):
    keep=[]
    def iou(a,b):
        ax,ay,aw,ah=a;bx,by,bw,bh=b
        o=max(0,min(ax+aw,bx+bw)-max(ax,bx))*max(0,min(ay+ah,by+bh)-max(ay,by))
        return o/(aw*ah+bw*bh-o)
    rows=sorted(rows,key=lambda r:-r[0])
    for score,index,box in rows:
        if all(iou(box,b)<.5 for _,_,b in keep):keep.append((score,index,box))
    return keep


def proposals(net,blob):
    net.setInput(blob);out=np.squeeze(net.forward())
    if out.ndim!=2:raise ValueError('unexpected output rank')
    if out.shape[0]<out.shape[1]:out=out.T
    rows=[]
    for row in out:
        scores=row[4:16];index=int(np.argmax(scores));confidence=float(scores[index])
        if confidence<THRESHOLD:continue
        cx,cy,w,h=(float(v) for v in row[:4])
        rows.append((confidence,index,[cx-w/2,cy-h/2,w,h]))
    return nms(rows)


def square(patch):
    return cv2.dnn.blobFromImage(patch,1/255.0,(640,640),swapRB=True,crop=False)


def letterbox(patch,size=640):
    h,w=patch.shape[:2];scale=min(size/h,size/w)
    nh,nw=int(round(h*scale)),int(round(w*scale))
    resized=cv2.resize(patch,(nw,nh),interpolation=cv2.INTER_LINEAR)
    canvas=np.full((size,size,3),114,np.uint8)
    top,left=(size-nh)//2,(size-nw)//2
    canvas[top:top+nh,left:left+nw]=resized
    return cv2.dnn.blobFromImage(canvas,1/255.0,(size,size),swapRB=True,crop=False),dict(scale=scale,pad=(left,top))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--frames',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    net=cv2.dnn.readNetFromONNX(str(args.model))
    report=dict(model_sha256=digest(args.model),threshold=THRESHOLD,
        square_preprocessing='cv2.dnn.blobFromImage(patch,(640,640),crop=False)',
        letterbox_preprocessing='aspect-preserving resize onto 640 canvas, pad 114',
        held_out_accuracy_verified=False,production_enabled=False,input_sent=False)
    frames=[]
    for item in json.load(open(args.frames,encoding='utf-8')):
        frame=local_file(ROOT,item['frame']);record=json.load(open(frame,encoding='utf-8'))
        image=local_file(ROOT,str(frame.with_suffix('.png')))
        pixels=cv2.imread(str(image))
        rows=[]
        for candidate in verified_card_rois(pixels,record):
            x,y,w,h=candidate['roi'];patch=pixels[max(0,y):y+h,max(0,x):x+w]
            sq=proposals(net,square(patch))
            lb,meta=letterbox(patch);lbr=proposals(net,lb)
            rows.append(dict(grid_slot=candidate['grid_slot'],roi=candidate['roi'],
                square_top=LABELS[sq[0][1]] if sq else None,
                square_score=round(sq[0][0],4) if sq else None,
                letterbox_top=LABELS[lbr[0][1]] if lbr else None,
                letterbox_score=round(lbr[0][0],4) if lbr else None,
                square_count=len(sq),letterbox_count=len(lbr),
                agrees=bool(sq and lbr and sq[0][1]==lbr[0][1])))
        frames.append(dict(frame=str(frame),scene=record.get('scene'),rows=rows))
    report['frames']=frames
    agree=sum(1 for f in frames for r in f['rows'] if r['agrees'])
    total=sum(len(f['rows']) for f in frames)
    report['agreements']=agree;report['cards']=total
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(out=str(args.out),cards=total,agreements=agree)))


if __name__=='__main__':main()
