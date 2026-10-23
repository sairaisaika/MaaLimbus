"""Research bootstrap: native sinner seals + measured visible card borders, no device.

Each cropped real card is labeled from a native TemplateMatch against a seal
whose class comes from an independently verified owned-gallery header. Whole-run
episode mappings are explicit, never invented from frame directory timestamps.
"""
import pathlib as _pathlib
import sys as _sys
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1] / 'src'))
import argparse,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.replay import ReplayController
from maalimbus.learning_dataset import local_file,digest
from maalimbus.owned_inventory import owned_page
from maalimbus.sinner_detection import LABELS
from maalimbus.sinner_dataset import manifest,export


def measured_border(image,cell):
    from maalimbus.neural_shadow import measured_card_border
    return measured_card_border(image,cell)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frames',type=Path,required=True,help='JSON rows with frame and authoritative run episode')
    p.add_argument('--inventory',type=Path,default=ROOT/'build/private-owned-inventory.json')
    p.add_argument('--maafw',type=Path,default=ROOT/'dist/MaaLimbus/maafw')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('New research output required')
    rows=read_json(a.frames);inventory=read_json(a.inventory)
    import cv2,numpy as np
    from maa.library import Library
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.controller import CustomController
    from maa.pipeline import JRecognitionType,JTemplateMatch
    from maalimbus.jobs import wait_job
    class Offline(ReplayController):
        def __init__(self):
            super().__init__(np.zeros((640,640,3),np.uint8))
    Library.open(a.maafw,agent_server=False);accepted=[];rejected=[];templates=[]
    a.out.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='maalimbus-native-teachers-') as directory:
        bundle=Path(directory);(bundle/'image').mkdir()
        for page in inventory['sinners']:
            frame=local_file(ROOT,page['frame']);record=read_json(frame)
            image=local_file(ROOT,str(frame.with_suffix('.png')))
            if digest(frame)!=page['frame_sha256'] or digest(image)!=page['image_sha256']:
                raise ValueError('Owned-gallery source binding changed')
            sinner=owned_page(record);pixels=cv2.imread(str(image))
            # This is the shared circular sinner emblem, not identity artwork.
            patch=pixels[147:191,435:475]
            template=bundle/f'image/{LABELS[sinner-1]}.png';cv2.imwrite(str(template),patch)
            templates.append(dict(sinner=sinner,path=template.name,source_frame=str(frame),
                source_record_sha256=digest(frame),source_image_sha256=digest(image),
                template_sha256=digest(template),source_crop=[435,147,40,44]))
        if {t['sinner'] for t in templates}!=set(range(1,13)):raise ValueError('Twelve independent gallery headers required')
        resource=Resource();wait_job(resource.post_bundle(bundle),timeout=30)
        controller=Offline();wait_job(controller.post_connection(),timeout=10)
        tasker=Tasker()
        if not tasker.bind(resource,controller):raise ValueError('Offline native binding failed')
        for row in rows:
            frame=local_file(ROOT,row['frame']);record=read_json(frame);image=local_file(ROOT,str(frame.with_suffix('.png')))
            scope_proof=local_file(ROOT,row['scope_proof']);scope=read_json(scope_proof,limit=16*1024*1024)
            if (scope_proof.parent!=frame.parent or
                    (scope.get('run_ledger') or {}).get('run')!=row.get('episode')):
                raise ValueError('Authoritative actual run episode proof differs')
            if record.get('scene')!='PRE_BATTLE_TEAM' or record.get('size')!=[1920,1080] or digest(image)!=record.get('image_sha256'):
                rejected.append(dict(frame=str(frame),reason='independent_prebattle_frame_required'));continue
            pixels=cv2.imread(str(image))
            native_by_slot={n:[] for n in range(12)}
            for t in templates:
                job=tasker.post_recognition(JRecognitionType.TemplateMatch,
                    JTemplateMatch(template=[t['path']],roi=[340,205,1220,605],threshold=[.9]),pixels)
                wait_job(job,timeout=30);detail=job.get()
                reco=detail.nodes[-1].recognition if detail and detail.nodes else None
                for hit in reco.filtered_results if reco and reco.hit else []:
                    hx,hy,hw,hh=hit.box
                    candidates=[n for n in range(12) if
                        abs(hx+hw/2-(510+(n%6)*198))<35 and
                        abs(hy+hh/2-(240+(n//6)*298))<35]
                    if len(candidates)==1:native_by_slot[candidates[0]].append((float(hit.score),t))
            for slot in range(12):
                column,rank=slot%6,slot//6;cell=[350+column*198,225+rank*298,185,273]
                border=measured_border(pixels,cell)
                if border is None:
                    rejected.append(dict(frame=str(frame),slot=slot+1,reason='four_visible_card_borders_unproven'));continue
                native=native_by_slot[slot]
                if len(native)!=1:
                    rejected.append(dict(frame=str(frame),slot=slot+1,reason='unique_native_sinner_seal_unproven'));continue
                score,teacher=native[0];bx,by,bw,bh=border[0]
                crop=[max(0,bx-12),max(0,by-25),bw+30,bh+39];x,y,w,h=crop
                key=digest(frame)+'-'+str(slot+1);target=a.out/f'{key}.png';proof=a.out/f'{key}.json'
                cv2.imwrite(str(target),pixels[y:y+h,x:x+w])
                boxes=[dict(label=LABELS[teacher['sinner']-1],box=[bx-x,by-y,bw,bh])]
                annotation=dict(frame=target.resolve().relative_to(ROOT).as_posix(),
                    proof=proof.resolve().relative_to(ROOT).as_posix(),episode=row['episode'],
                    locale='en',boxes=boxes,reviewed=True,complete=True)
                write_json(proof,dict(annotation,image_sha256=digest(target),
                    review_method='native_sinner_seal_and_pixel_card_edges',research_only=True,
                    source_frame=frame.relative_to(ROOT).as_posix(),source_record_sha256=digest(frame),
                    source_image_sha256=digest(image),crop=crop,border_scores=border[1],
                    scope_proof=scope_proof.relative_to(ROOT).as_posix(),scope_proof_sha256=digest(scope_proof),
                    native_seal_score=score,native_seal_teacher=teacher,input_authorized=False))
                accepted.append(annotation)
    data=manifest(ROOT,accepted,minimum=20)
    write_json(a.out/'annotations.json',accepted);write_json(a.out/'manifest.json',data)
    write_json(a.out/'audit.json',dict(accepted=len(accepted),rejected=rejected,
        class_sources=templates,research_only=True,game_controller=False,input_sent=False))
    if any(s['split']=='train' for s in data['samples']):export(ROOT,data,a.out/'dataset',research=True)
    print(json.dumps(dict(samples=len(accepted),episodes=data['episodes'],coverage=data['coverage'],
        research_only=True,training_ready=False,output=str(a.out))))


if __name__=='__main__':main()
