"""Bootstrap real twelve-class research labels from native verified owned galleries.

Every gallery card shares its independently recognized sinner header; neither
fixed slot position nor a Wiki identity implies that class. Four visible border
strips are measured before making a real-pixel crop. One collection round remains
ONE episode, even though twelve pages were captured; this is research only.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.owned_inventory import owned_page
from maalimbus.learning_dataset import local_file,digest
from maalimbus.sinner_detection import LABELS
from maalimbus.sinner_dataset import manifest,export
from autolabel_sinner_retained import measured_border


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory',type=Path,default=ROOT/'build/private-owned-inventory.json')
    p.add_argument('--collection-proof',type=Path,default=ROOT/'build/sinner-inventory-navigation.json')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();inventory=read_json(a.inventory);proof=local_file(ROOT,a.collection_proof)
    episode='owned-gallery-'+digest(proof)
    if a.out.exists():raise ValueError('New output required')
    import cv2
    a.out.mkdir(parents=True);accepted=[];rejected=[]
    for page in inventory['sinners']:
        frame=local_file(ROOT,page['frame']);record=read_json(frame);image=local_file(ROOT,str(frame.with_suffix('.png')))
        if digest(frame)!=page['frame_sha256'] or digest(image)!=page['image_sha256']:
            raise ValueError('Native inventory source changed')
        sinner=owned_page(record);pixels=cv2.imread(str(image))
        for slot in range(18):
            column,rank=slot%6,slot//6
            border=measured_border(pixels,[280+207*column,150+289*rank,188,273])
            if border is None:
                rejected.append(dict(sinner_index=sinner,slot=slot+1,reason='four_visible_card_borders_unproven'));continue
            bx,by,bw,bh=border[0];x,y=max(0,bx-10),max(0,by-10);w,h=bw+20,bh+20
            key=f'{sinner:02}-{slot:02}';target=a.out/f'{key}.png';review=a.out/f'{key}.json'
            cv2.imwrite(str(target),pixels[y:y+h,x:x+w]);boxes=[dict(label=LABELS[sinner-1],box=[bx-x,by-y,bw,bh])]
            row=dict(frame=target.resolve().relative_to(ROOT).as_posix(),proof=review.resolve().relative_to(ROOT).as_posix(),
                episode=episode,locale='en',boxes=boxes,reviewed=True,complete=True)
            write_json(review,dict(row,image_sha256=digest(target),review_method='native_sinner_seal_and_pixel_card_edges',
                gallery_teacher=True,sinner_index=sinner,research_only=True,
                source_frame=frame.relative_to(ROOT).as_posix(),source_record_sha256=digest(frame),
                source_image_sha256=digest(image),crop=[x,y,w,h],border_scores=border[1],
                scope_proof=proof.relative_to(ROOT).as_posix(),scope_proof_sha256=digest(proof),input_authorized=False))
            accepted.append(row)
    data=manifest(ROOT,accepted);write_json(a.out/'annotations.json',accepted);write_json(a.out/'manifest.json',data)
    write_json(a.out/'audit.json',dict(samples=len(accepted),coverage=data['coverage'],
        one_authoritative_episode=episode,rejected=rejected,model_trained=False,
        production_enabled=False,input_sent=False,game_controller=False))
    if any(s['split']=='train' for s in data['samples']):export(ROOT,data,a.out/'dataset',research=True)
    print(json.dumps(dict(samples=len(accepted),episodes=data['episodes'],coverage=data['coverage'],research_only=True)))


if __name__=='__main__':main()
