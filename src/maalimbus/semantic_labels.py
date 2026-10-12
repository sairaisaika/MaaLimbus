"""Automatic native-teacher semantic proposals, separate from NN predictions."""
from .storage import read_json
from .learning_dataset import local_file,digest
from .owned_inventory import owned_page,reconcile_titles
from pathlib import Path
import hashlib,json


def collect(root,index_path,inventory_path):
    index_file=local_file(root,index_path);index=read_json(index_file)
    inventory=read_json(local_file(root,inventory_path))
    if inventory['index_sha256']!=digest(index_file):raise ValueError('Inventory catalogue revision changed')
    lookup={x['id']:x for x in index['identities']};labels=[]
    for page in inventory['sinners']:
        frame=local_file(root,page['frame']);record=read_json(frame)
        image=local_file(root,str(frame.with_suffix('.png')))
        if digest(frame)!=page['frame_sha256'] or digest(image)!=page['image_sha256']:
            raise ValueError('Native teacher evidence changed')
        if record.get('image_sha256')!=digest(image) or owned_page(record)!=page['sinner_index']:
            raise ValueError('Independent owned-page teacher differs')
        actual=reconcile_titles(index,page['sinner_index'],record['inventory_observations'],record.get('inventory_locale','en'))
        if actual['owned']!=page['owned']:raise ValueError('Owned identity reconciliation changed')
        for owned in actual['owned']:
            item=lookup[owned['id']];systems=item.get('wiki_systems')
            labels.append(dict(kind='owned_identity_semantics',personality_id=item['id'],
                sinner_index=item['sinner_index'],owned=True,level=owned['level'],uptie=owned['uptie'],
                systems=systems['keywords'] if systems is not None else None,
                unknown_systems=systems['unknown_keywords'] if systems is not None else None,
                teacher='native_owned_filter_and_exact_title_plus_revisioned_wiki_id',
                catalogue_sha256=digest(index_file),frame=str(frame),frame_sha256=digest(frame),
                image_sha256=digest(image),reviewed=False,training_eligible=False,
                model_applied=False,input_authorized=False))
    return dict(schema_version=1,labels=labels,automatic_teacher_proposals=True,
        neural_predictions=False,model_trained=False,training_eligible=False,
        inventory_complete=inventory['inventory_complete'],unobserved_ownership='unknown')


def persist_frame_proposals(root,frame_path,episode,locale,out):
    """Continuous Mirror observation hook; writes only a content-addressed queue.

    Scene OCR, Wiki semantic labels and model predictions are separate teachers.
    None may turn their own boxes into reviewed training truth. This function
    never opens a controller or changes run/account/settings state.
    """
    from .storage import write_json
    from .sinner_detection import proposals
    import cv2
    if not isinstance(episode,str) or not episode or locale not in ('en','jp'):
        raise ValueError('Actual run episode and supported locale required')
    root=Path(root).resolve();frame=local_file(root,frame_path)
    record=read_json(frame);image=local_file(root,str(frame.with_suffix('.png')))
    sha=digest(image);pixels=cv2.imread(str(image))
    if pixels is None or sha!=record.get('image_sha256') or record.get('size')!=[pixels.shape[1],pixels.shape[0]]:
        raise ValueError('Decodable actual Maa frame/PNG hash and size required')
    neural=record.get('neural_sinners') or {};boxes=[]
    if neural.get('status')=='shadow':
        # Revalidate native output rather than trusting serialized proposal flags.
        boxes=proposals(record,[dict(class_index=b['class_id'],box=b['box'],score=b['score'])
                                for b in neural.get('boxes',[])])
    gallery=None
    try:gallery=owned_page(record)
    except ValueError:pass
    result=dict(schema_version=1,episode=episode,locale=locale,
        frame=image.relative_to(root).as_posix(),image_sha256=sha,
        native_record=frame.relative_to(root).as_posix(),native_record_sha256=digest(frame),
        scene_proposal=record.get('scene','UNKNOWN'),scene_teacher='native_caption_observer_not_ground_truth',
        boxes=boxes,model_sha256=neural.get('model_sha256'),
        gallery_sinner_index=gallery,identity_observations=record.get('inventory_observations',[]) if gallery else [],
        reviewed=False,complete=False,training_eligible=False,input_authorized=False)
    key=hashlib.sha256((episode+'\0'+digest(frame)+'\0'+sha).encode()).hexdigest()
    import shutil
    folder=Path(out)/key;folder.mkdir(parents=True,exist_ok=True)
    destination=folder/'proposal.json'
    if destination.exists():
        if read_json(destination)!=result:raise ValueError('Conflicting immutable proposal record')
    else:write_json(destination,result)
    for original,name in ((frame,'frame.json'),(image,'frame.png')):
        copied=folder/name
        if copied.exists() and digest(copied)!=digest(original):
            raise ValueError('Conflicting immutable frame-review bytes')
        if not copied.exists():shutil.copyfile(original,copied)
    review=folder/'review.json'
    if not review.exists():write_json(review,dict(status='pending',approved=False,corrected_boxes=[],corrected_scene=None,notes=''))
    (folder/'trace.log').write_text('Episode: '+episode+'\nScene proposal: '+result['scene_proposal']+
        '\nModel: '+str(result['model_sha256'])+'\nUnreviewed neural boxes: '+str(len(boxes))+'\n',encoding='utf-8')
    return dict(status='queued',proposal=str(destination),proposal_sha256=digest(destination),
        candidate_boxes=len(boxes),training_eligible=False,model_applied=bool(boxes),input_authorized=False)


def candidate_transition(root,episode,locale,observation,out):
    """Candidate label for a success transition on a page no teacher explains.

    Bounded exploration is the run owner's job; this records the operation
    evidence that surrounds a claimed success and emits only a *candidate*
    label. A native success assertion (``role='success'``) is required, the
    before/after evidence must be two distinct retained frames of one episode,
    and every deviation the owner declares is carried through as an open
    unknown. Nothing here is reviewed, training-eligible or production, and no
    label can approve itself, the same fail-closed posture as map routing.
    """
    observation=observation or {}
    for key,label in (('episode',episode),('locale',locale)):
        if not isinstance(label,str) or not label.strip():raise ValueError(f'Actual {key} required')
    if locale not in ('en','jp'):raise ValueError('Supported locale required')
    if not isinstance(observation.get('page'),str) or not observation['page'].strip():
        raise ValueError('Observed page identity required')
    allowed=observation.get('allowed_operations')
    if not isinstance(allowed,list) or not allowed or any(not isinstance(a,str) or not a.strip() for a in allowed):
        raise ValueError('Bounded allowed_operations required')
    if observation.get('bounded') is not True:raise ValueError('Exploration must be declared bounded')
    steps=observation.get('steps_used');limit=observation.get('step_limit')
    if not isinstance(limit,int) or isinstance(limit,bool) or limit<1 or not isinstance(steps,int) or isinstance(steps,bool) or not 0<=steps<=limit:
        raise ValueError('Integer step budget within the declared limit required')
    root=Path(root).resolve();states=[]
    for role in ('before','after'):
        value=observation.get(f'{role}_frame')
        if not isinstance(value,str) or not value.strip():raise ValueError(f'{role} frame required')
        frame=local_file(root,value)
        if Path(value).is_absolute() or (root/frame).resolve()!=Path(frame).resolve():
            raise ValueError(f'{role} frame must be a workspace-relative retained capture')
        record=read_json(frame);image=local_file(root,str(frame.with_suffix('.png')))
        sha=digest(image)
        if record.get('image_sha256')!=sha:raise ValueError(f'{role} PNG binding differs')
        states.append(dict(role=role,frame=frame,image=image,record=record,sha=sha))
    before,after=states
    if before['sha']==after['sha']:raise ValueError('Two distinct retained captures required')
    stamps=[]
    for state in states:
        stamp=state['record'].get('utc')
        if not isinstance(stamp,str) or not stamp:raise ValueError('Independent capture time required')
        stamps.append(stamp)
    if stamps[0]>=stamps[1]:raise ValueError('After evidence must follow before evidence')
    if before['record'].get('scene')==after['record'].get('scene'):
        raise ValueError('A success transition must change the observed page')
    assertion=observation.get('success_assertion') or {}
    if assertion.get('verified') is not True:
        raise ValueError('Independent postcondition verification required for a success')
    if assertion.get('role')!='success':
        raise ValueError('Only a verified success assertion may carry a candidate transition')
    if not isinstance(assertion.get('postcondition'),str) or not assertion['postcondition'].strip():
        raise ValueError('Native success postcondition text required')
    action=observation.get('action') or {}
    if action.get('kind') not in allowed:
        raise ValueError('Operation is outside the declared bounded set')
    unknowns=list(observation.get('unknowns') or [])
    for deviation in list(observation.get('deviations') or []):
        unknowns.append(dict(kind='deviation',detail=str(deviation),resolved=False))
    if not unknowns:
        unknowns.append(dict(kind='unclassified_state_change',
            detail='page changed without a declared explanation',resolved=False))
    proposal=dict(schema_version=1,kind='success_transition_candidate',
        episode=episode,locale=locale,page=observation['page'],
        candidate_label=assertion.get('candidate_label'),
        transition=dict(from_scene=before['record'].get('scene'),to_scene=after['record'].get('scene'),
            action=dict(kind=action.get('kind'),target=action.get('target'),reason=action.get('reason')),
            expected_effect=action.get('expected_effect'),postcondition=assertion['postcondition'],
            success_assertion=dict(teacher=assertion.get('teacher'),
                evidence=assertion.get('evidence'),role='success',verified=True)),
        before=dict(frame=before['frame'].relative_to(root).as_posix(),frame_sha256=digest(before['frame']),
            image_sha256=before['sha'],utc=stamps[0],scene=before['record'].get('scene')),
        after=dict(frame=after['frame'].relative_to(root).as_posix(),frame_sha256=digest(after['frame']),
            image_sha256=after['sha'],utc=stamps[1],scene=after['record'].get('scene')),
        exploration=dict(allowed_operations=list(allowed),bounded=True,steps_used=steps,step_limit=limit),
        unknowns=unknowns,unknown_count=len(unknowns),
        status='candidate_pending_human_review',reviewed=False,human_reviewed=False,
        training_eligible=False,production=False,promotable=False,
        promotion_rule='A human must approve the observed transition before this candidate can become a label.',
        model_applied=False,input_authorized=False,input_sent=False,
        teacher='run_owner_operation_evidence_plus_independent_postcondition')
    from .storage import write_json
    out=Path(out)
    if out.suffix.lower()=='.json':
        destination=out;directory=out.parent
    else:
        key=hashlib.sha256((episode+'\0'+before['sha']+'\0'+after['sha']).encode()).hexdigest()
        directory=out;destination=out/f'transition-{key}.json'
    directory.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        if read_json(destination)!=proposal:raise ValueError('Conflicting immutable transition candidate')
    else:write_json(destination,proposal)
    return dict(status='candidate_pending_human_review',candidate=str(destination),
        candidate_sha256=digest(destination),promotable=False,reviewed=False,
        training_eligible=False,production=False,input_authorized=False)


def review_gallery_pair(root,index_path,before_path,after_path,episode,locale,out):
    """Automatic review from independent native identity + four card-corner teachers.

    The collector must supply ``inventory_cards`` and
    ``inventory_card_boundary_complete`` from native TemplateMatch, NOT NN boxes
    or fixed slot hypotheses. Exact IDs are reconciled independently from OCR.
    Existing captures lacking those measurements are refused rather than guessed.
    """
    import datetime,re,cv2
    from .storage import write_json
    from .owned_inventory import normalized
    from .sinner_detection import LABELS,box
    root=Path(root).resolve();index_file=local_file(root,index_path);index=read_json(index_file)
    if not episode or locale not in ('en','jp'):raise ValueError('Real episode/locale required')
    states=[]
    for path in (before_path,after_path):
        frame=local_file(root,path);record=read_json(frame);image=local_file(root,str(frame.with_suffix('.png')))
        pixels=cv2.imread(str(image))
        if pixels is None or digest(image)!=record.get('image_sha256') or record.get('size')!=[pixels.shape[1],pixels.shape[0]]:
            raise ValueError('Gallery PNG binding differs')
        sinner=owned_page(record)
        if record.get('inventory_card_boundary_complete') is not True:
            raise ValueError('Complete native card boundary enumeration required')
        observations=record.get('inventory_observations',[])
        matches=reconcile_titles(index,sinner,observations,locale)
        cards=record.get('inventory_cards')
        if not isinstance(cards,list) or not cards or matches['unresolved'] or len(cards)!=len(observations):
            raise ValueError('Every visible card requires complete known native title/boundary')
        expected={row['id'] for row in matches['owned']};seen=set();boxes=[]
        for card in cards:
            identity=card.get('identity_id');entry=next((x for x in index['identities'] if x['id']==identity),None)
            if (identity not in expected or identity in seen or not entry or entry['sinner_index']!=sinner or
                    normalized(card.get('title',''))!=normalized(entry['titles'].get(locale,'')) or
                    card.get('title_score',0)<.9):raise ValueError('Native exact identity teacher differs')
            seen.add(identity);boundary=box(card['box'],record['size']);x,y,w,h=boundary
            corners=card.get('corners',{})
            if set(corners)!=set(('top_left','top_right','bottom_left','bottom_right')):
                raise ValueError('Four independent visible card corners required')
            for name,corner in corners.items():
                if (corner.get('recognizer')!='TemplateMatch' or corner.get('unique') is not True or
                        corner.get('score',0)<.95 or not re.fullmatch(r'[0-9a-f]{64}',corner.get('template_sha256',''))):
                    raise ValueError('Native unique high-confidence corner teacher required')
                cx,cy,cw,ch=box(corner['box'],record['size'])
                px,py=cx+cw/2,cy+ch/2
                tx=x+(w if name.endswith('right') else 0);ty=y+(h if name.startswith('bottom') else 0)
                if abs(px-tx)>.15*w or abs(py-ty)>.15*h or cw>.25*w or ch>.25*h:
                    raise ValueError('Corner measurement does not bound actual card')
            boxes.append(dict(label=LABELS[sinner-1],box=boundary))
        stamp=datetime.datetime.fromisoformat(record['utc'])
        if stamp.tzinfo is None:raise ValueError('Actual timezone-aware capture time required')
        states.append(dict(frame=frame,image=image,record=record,sinner=sinner,boxes=boxes,stamp=stamp))
    before,after=states
    if ((after['stamp']-before['stamp']).total_seconds()<1 or before['frame']==after['frame'] or
            before['sinner']!=after['sinner'] or before['boxes']!=after['boxes'] or
            before['record']['inventory_cards']!=after['record']['inventory_cards']):
        raise ValueError('Independent fresh gallery teachers disagree')
    out=Path(out);proof=out/'review.json'
    row=dict(frame=after['image'].relative_to(root).as_posix(),proof=str(proof.resolve().relative_to(root)),
        episode=episode,locale=locale,boxes=after['boxes'],reviewed=True,complete=True)
    write_json(proof,dict(row,image_sha256=digest(after['image']),
        review_method='independent_native_teachers',
        teacher='exact_owned_header_full_title_and_four_native_card_corners_two_captures',
        before_record=before['frame'].relative_to(root).as_posix(),before_record_sha256=digest(before['frame']),
        before_image_sha256=digest(before['image']),after_record=after['frame'].relative_to(root).as_posix(),
        after_record_sha256=digest(after['frame']),catalogue=index_file.relative_to(root).as_posix(),
        catalogue_sha256=digest(index_file),input_authorized=False))
    return row
