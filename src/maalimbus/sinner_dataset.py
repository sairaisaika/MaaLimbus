"""Reviewed sinner-card detection dataset, split by episode and bound to PNGs."""
import hashlib,json
from collections import Counter
from pathlib import Path
import cv2
from .learning_dataset import local_file,digest
from .sinner_detection import LABELS,box


def split(episode):
    bucket=int(hashlib.sha256(episode.encode()).hexdigest()[:8],16)%10
    return 'test' if bucket==0 else ('validation' if bucket<3 else 'train')


def manifest(root,annotations,minimum=20):
    root=Path(root).resolve();samples=[];seen={};episodes={}
    if type(minimum) is not int or minimum<1:raise ValueError('Positive coverage count required')
    for row in annotations:
        if row.get('reviewed') is not True or row.get('complete') is not True:
            raise ValueError('Complete independent review required, including negatives')
        episode=row.get('episode');locale=row.get('locale')
        if not isinstance(episode,str) or not episode or locale not in ('en','jp'):
            raise ValueError('Episode and supported locale required')
        frame=local_file(root,row['frame']);proof=local_file(root,row['proof'])
        sha=digest(frame);review=json.loads(proof.read_text(encoding='utf-8'))
        if frame.suffix.lower()!='.png' or frame.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n':
            raise ValueError('Maa PNG capture required')
        image=cv2.imread(str(frame))
        if image is None:raise ValueError('Real decodable image required')
        size=[image.shape[1],image.shape[0]]
        boxes=[]
        for item in row.get('boxes',[]):
            label=item.get('label')
            if label not in LABELS:raise ValueError('Unknown sinner label')
            boxes.append(dict(label=label,class_id=LABELS.index(label),box=box(item.get('box'),size)))
        if (review.get('image_sha256')!=sha or review.get('episode')!=episode or
                review.get('reviewed') is not True or review.get('complete') is not True or
                review.get('boxes')!=row.get('boxes',[]) or review.get('locale')!=locale or
                review.get('review_method') not in ('human_card_boundary','independent_native_teachers',
                                                   'native_sinner_seal_and_pixel_card_edges')):
            raise ValueError('Independent review does not bind this frame and exact boxes')
        if review.get('review_method')=='native_sinner_seal_and_pixel_card_edges':
            original=local_file(root,review['source_frame']);original_image=local_file(root,str(original.with_suffix('.png')))
            if digest(original)!=review['source_record_sha256'] or digest(original_image)!=review['source_image_sha256']:
                raise ValueError('Original automatic teacher evidence changed')
            scope_file=local_file(root,review['scope_proof'])
            if digest(scope_file)!=review['scope_proof_sha256']:raise ValueError('Authoritative real episode changed')
            if review.get('gallery_teacher') is True:
                from .owned_inventory import owned_page
                source=json.loads(original.read_text(encoding='utf-8'))
                if owned_page(source)!=review['sinner_index'] or any(b['label']!=LABELS[review['sinner_index']-1] for b in boxes):
                    raise ValueError('Independent native gallery class changed')
                if episode!='owned-gallery-'+digest(scope_file):raise ValueError('Gallery episode proof differs')
            else:
                scope_record=json.loads(scope_file.read_text(encoding='utf-8'))
                if scope_file.parent!=original.parent or (scope_record.get('run_ledger') or {}).get('run')!=episode:
                    raise ValueError('Authoritative real episode changed')
            pixels=cv2.imread(str(original_image));x,y,w,h=review['crop']
            if pixels is None or not (pixels[y:y+h,x:x+w].shape==image.shape and
                                      (pixels[y:y+h,x:x+w]==image).all()):
                raise ValueError('Automatic training crop no longer matches actual pixels')
            if review.get('research_only') is not True:
                raise ValueError('Automatic pixel-boundary bootstrap is research only')
        identity=(episode,locale,boxes)
        if sha in seen:
            if seen[sha]!=identity:raise ValueError('Conflicting duplicate or episode leakage')
            continue
        seen[sha]=identity;partition=split(episode);episodes[episode]=partition
        samples.append(dict(frame=frame.relative_to(root).as_posix(),image_sha256=sha,size=size,
            proof=proof.relative_to(root).as_posix(),proof_sha256=digest(proof),
            episode=episode,locale=locale,split=partition,boxes=boxes,
            research_only=review.get('research_only') is True))
    coverage={part:Counter(b['label'] for s in samples if s['split']==part for b in s['boxes'])
              for part in ('train','validation','test')}
    missing={p:[label for label in LABELS if counts[label]<minimum] for p,counts in coverage.items()}
    enough_episodes=all(sum(v==p for v in episodes.values())>=3 for p in coverage)
    return dict(version=1,labels=list(LABELS),samples=samples,episodes=episodes,
        coverage={p:dict(c) for p,c in coverage.items()},missing_classes=missing,
        training_ready=bool(samples) and enough_episodes and not any(missing.values()) and
            not any(s['research_only'] for s in samples),
        minimum_per_class=minimum,minimum_episodes_per_split=3,model_trained=False,
        production_enabled=False,input_authorized=False)


def export(root,data,out,*,research=False,native_resize=False):
    """Export hash-checked YOLO labels; reject incomplete data before creating files."""
    import shutil
    root=Path(root).resolve();out=Path(out).resolve()
    if out.exists():raise ValueError('Dataset destination must be new')
    if not data.get('training_ready') and not research:raise ValueError('Dataset coverage is not ready')
    if research and not any(s['boxes'] and s['split']=='train' for s in data['samples']):
        raise ValueError('Research still requires actual reviewed training instances')
    verified=manifest(root,[dict(s,reviewed=True,complete=True,boxes=[dict(label=b['label'],box=b['box']) for b in s['boxes']]) for s in data['samples']],data['minimum_per_class'])
    if verified!=data:raise ValueError('Dataset manifest or evidence changed')
    for sample in data['samples']:
        part=sample['split'];name=sample['image_sha256'];w,h=sample['size']
        image_dir=out/'images'/part;label_dir=out/'labels'/part
        image_dir.mkdir(parents=True,exist_ok=True);label_dir.mkdir(parents=True,exist_ok=True)
        if native_resize:
            # Pinned Maa detector uses direct INTER_AREA resize, not letterbox.
            pixels=cv2.imread(str(local_file(root,sample['frame'])))
            if not cv2.imwrite(str(image_dir/(name+'.png')),cv2.resize(pixels,(640,640),interpolation=cv2.INTER_AREA)):
                raise ValueError('Native-preprocessed image write failed')
        else:shutil.copyfile(local_file(root,sample['frame']),image_dir/(name+'.png'))
        lines=[]
        for b in sample['boxes']:
            x,y,bw,bh=b['box'];lines.append(f"{b['class_id']} {(x+bw/2)/w:.8f} {(y+bh/2)/h:.8f} {bw/w:.8f} {bh/h:.8f}")
        (label_dir/(name+'.txt')).write_text('\n'.join(lines),encoding='utf-8')
    config=dict(path=str(out),train='images/train',val='images/validation',test='images/test',names=list(LABELS))
    # JSON is valid YAML; avoids another training-only runtime dependency.
    (out/'data.yaml').write_text(json.dumps(config,indent=2),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    if research:(out/'research.json').write_text(json.dumps(dict(research_only=True,production_enabled=False)),encoding='utf-8')
    if native_resize:(out/'native-resize.json').write_text(json.dumps(dict(size=[640,640],interpolation='INTER_AREA',
        method='pinned_Maa_NeuralNetworkDetector_direct_resize')),encoding='utf-8')
    return out/'data.yaml'


def verify_export(root,out,*,research=False):
    """Bind actual training input bytes to reviewed evidence, not just a JSON flag."""
    out=Path(out).resolve();data=json.loads((out/'manifest.json').read_text())
    verified=manifest(root,[dict(s,reviewed=True,complete=True,boxes=[dict(label=b['label'],box=b['box']) for b in s['boxes']]) for s in data['samples']],data['minimum_per_class'])
    if verified!=data or (not data['training_ready'] and not research):raise ValueError('Dataset review/coverage changed')
    config=json.loads((out/'data.yaml').read_text())
    if config!=dict(path=str(out),train='images/train',val='images/validation',test='images/test',names=list(LABELS)):
        raise ValueError('Training configuration differs')
    expected={'data.yaml','manifest.json'}
    resized=(out/'native-resize.json').exists()
    if resized:
        if json.loads((out/'native-resize.json').read_text())!=dict(size=[640,640],interpolation='INTER_AREA',
                method='pinned_Maa_NeuralNetworkDetector_direct_resize'):
            raise ValueError('Native input preprocessing differs')
        expected.add('native-resize.json')
    if research:
        if json.loads((out/'research.json').read_text())!=dict(research_only=True,production_enabled=False):
            raise ValueError('Research export flag differs')
        expected.add('research.json')
    for s in data['samples']:
        name=s['image_sha256'];part=s['split'];w,h=s['size']
        image=f'images/{part}/{name}.png';label=f'labels/{part}/{name}.txt'
        expected.update((image,label))
        if resized:
            original=cv2.imread(str(local_file(Path(root).resolve(),s['frame'])))
            actual=cv2.imread(str(local_file(out,image)))
            wanted=cv2.resize(original,(640,640),interpolation=cv2.INTER_AREA)
            if actual is None or actual.shape!=wanted.shape or not (actual==wanted).all():
                raise ValueError('Exported native-resized training image changed')
        elif digest(local_file(out,image))!=name:raise ValueError('Exported training image changed')
        lines=[]
        for b in s['boxes']:
            x,y,bw,bh=b['box'];lines.append(f"{b['class_id']} {(x+bw/2)/w:.8f} {(y+bh/2)/h:.8f} {bw/w:.8f} {bh/h:.8f}")
        if local_file(out,label).read_text()!='\n'.join(lines):raise ValueError('Exported training labels changed')
    if {p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}!=expected:
        raise ValueError('Unlisted training data')
    return data
