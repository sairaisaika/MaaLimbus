"""Durable floor gift intents. Unknown postconditions never permit another input."""
import hashlib
import json
from pathlib import Path

from .storage import read_json, write_json

#: The page families that end a floor gift's pick sequence without another pick:
#: the theme-pack shelf and the map both mean this floor's gift step is over.
FINAL_SUCCESSOR_PAGES = ('THEME_PACKS', 'MAP')
#: Every page that can independently prove a floor gift receipt's successor. The
#: settling rule and the retained-evidence recovery path must accept the same set:
#: a proof one of them honours and the other does not is how a cleared notice
#: leaves a receipt that can never be booked.
RECEIPT_SUCCESSOR_PAGES = ('GIFT_GET', 'GIFT_PICK', 'REWARD_CARD') + FINAL_SUCCESSOR_PAGES


class FloorGiftTransaction:
    def __init__(self, path):
        self.path = path
        self.data = read_json(path) if path.exists() else None

    @staticmethod
    def signature(offers):
        value = [o.identity() for o in offers]
        return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

    def prepare(self, scope, offers, count, proof):
        signature = self.signature(offers)
        d = self.data
        if not d or d['scope']!=scope or d['offer']!=signature:
            if d and (d['pending'] or not d.get('completed')):
                raise ValueError('floor_gift_previous_transaction_unresolved')
            if count['chosen']!=0:
                raise ValueError('floor_gift_selected_without_scoped_evidence')
            history = (d.get('history',[])+[d]) if d else []
            if d: history[-1] = {k:v for k,v in d.items() if k!='history'}
            d = dict(scope=scope,offer=signature,required=count['required'],
                     selected=[],picked_owned={},pending=None,commit_sent=False,receipts=[],
                     substitutions=[],completed=False,proofs=[str(proof)],history=history)
            self.data=d
            write_json(self.path,d)
        if d['pending'] or d['commit_sent'] or d['completed'] or count['required']!=d['required'] or count['chosen']!=len(d['selected']):
            raise ValueError('floor_gift_pending_commit_or_counter_mismatch')
        return d

    def intent(self, title, count, proof, *, owned=False):
        d=self.data
        if d['pending'] or d['commit_sent'] or title in d['selected'] or count['chosen']!=len(d['selected']):
            raise ValueError('floor_gift_selection_would_repeat')
        d['pending']=dict(kind='pick',title=title,before=count['chosen'],proof=str(proof))
        # A gift the run already owns cannot be granted twice: the game answers such a
        # pick with a different gift under its own name (live: 'Portable Battery Socket'
        # came back as 'Faint Vestige').  The flag is kept so the receipt stage can label
        # the substitution instead of refusing a notice the game really printed.
        d.setdefault('picked_owned',{})[title]=bool(owned)
        path=Path(proof)
        if path.is_file() and path.with_suffix('.png').is_file():
            d['pending'].update(before_json_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                before_png_sha256=hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest())
        write_json(self.path,d)

    def recover_pick(self, scope, offers, count, proof, catalog):
        """Resolve one sent pick from its retained original and fresh exact counter.

        Does not replay input. Missing/changed original or unknown successor keeps
        pending intact. Older intents still require original PNG metadata and the
        complete offer signature, never a saved default or a guessed selection.
        """
        from .floor_gifts import observe
        from .vision import Text
        d=self.data;pending=(d or {}).get('pending')
        if not pending or pending['kind']!='pick' or d['scope']!=scope:
            raise ValueError('floor_gift_recovery_scope_or_pick_not_proven')
        before=Path(pending['proof']); original=read_json(before)
        old_hash=hashlib.sha256(before.with_suffix('.png').read_bytes()).hexdigest()
        if old_hash!=original.get('image_sha256') or original.get('scene')!='GIFT_PICK':
            raise ValueError('floor_gift_original_pick_png_not_proven')
        if pending.get('before_png_sha256',old_hash)!=old_hash or pending.get(
                'before_json_sha256',hashlib.sha256(before.read_bytes()).hexdigest())!=hashlib.sha256(before.read_bytes()).hexdigest():
            raise ValueError('floor_gift_original_pick_proof_changed')
        old_offers,old_count=observe([Text(r['text'],tuple(r['box']),r['score']) for r in original['ocr']],original['size'],catalog)
        fresh=read_json(Path(proof)); fresh_hash=hashlib.sha256(Path(proof).with_suffix('.png').read_bytes()).hexdigest()
        if fresh_hash!=fresh.get('image_sha256') or fresh_hash==old_hash or fresh.get('scene')!='GIFT_PICK':
            raise ValueError('floor_gift_fresh_pick_successor_not_proven')
        if (self.signature(old_offers)!=d['offer'] or old_count!={'chosen':pending['before'],'required':d['required']}
                or pending['title'] not in [o.title for o in old_offers if not o.unpriced]):
            raise ValueError('floor_gift_original_pick_offer_not_proven')
        self.observe_pick(offers,count,proof)

    def observe_pick(self, offers, count, proof):
        d=self.data; p=d['pending']
        if not p or p['kind']!='pick' or self.signature(offers)!=d['offer'] or count!={'chosen':p['before']+1,'required':d['required']}:
            raise ValueError('floor_gift_selection_postcondition_not_proven')
        d['selected'].append(p['title']);d['pending']=None
        d['proofs'].append(str(proof));write_json(self.path,d)

    def commit(self, proof):
        d=self.data
        if d['pending'] or d['commit_sent'] or len(d['selected'])!=d['required']:
            raise ValueError('floor_gift_commit_not_ready')
        d['commit_sent']=True
        d['pending']=dict(kind='commit',proof=str(proof))
        write_json(self.path,d)

    def refuse_owned(self, offers, count, proof):
        d=self.data
        if (d['pending'] or d['commit_sent'] or d['selected'] or d['completed']
            or count!={'chosen':0,'required':1} or self.signature(offers)!=d['offer']
            or len(offers)!=1 or not offers[0].owned
            or offers[0].selection_source!='single_free_select_button'):
            raise ValueError('floor_gift_owned_refusal_not_proven')
        d['pending']=dict(kind='refuse_owned',title=offers[0].title,proof=str(proof))
        write_json(self.path,d)

    def observe_refusal(self, page, proof, *, map_floor=None, next_reward_offer=None):
        d=self.data;p=d['pending']
        if not p or p['kind']!='refuse_owned':raise ValueError('floor_gift_refusal_intent_missing')
        known_map=page=='MAP' and map_floor in range(1,6)
        known_reward=(page=='REWARD_CARD' and next_reward_offer
            and next_reward_offer.get('count')=={'chosen':0,'required':1}
            and next_reward_offer.get('title')=='Select Encounter Reward Card')
        if not (known_map or known_reward):raise ValueError('floor_gift_refusal_successor_not_proven')
        d['refusal']=dict(title=p['title'],before=p['proof'],successor=str(proof))
        d['completed']=True;d['pending']=None
        write_json(self.path,d)

    def refusal_confirm_intent(self, scope, proof):
        d=self.data;p=d.get('pending')
        if d['scope']!=scope or not p or p['kind']!='refuse_owned' or p.get('confirm_sent'):
            raise ValueError('floor_gift_refusal_confirm_would_repeat')
        p.update(confirm_sent=True,confirm_proof=str(proof));write_json(self.path,d)


    def receipt_intent(self, title, proof):
        from .initial_gifts import same_name
        d=self.data;p=d.get('pending')
        expected=[n for n in d['selected'] if same_name(n,title)]
        seen=[r['title'] for r in d['receipts']]
        printed=(p or {}).get('granted')
        if not expected and printed and same_name(printed,title):
            # The notice prints the name the game substituted for the next unclaimed
            # pick; the pick itself is still the one this run chose.
            unclaimed=[n for n in d['selected'] if n not in seen]
            if len(unclaimed)==1:expected=unclaimed
        if not d['commit_sent'] or not p or p['kind']!='commit' or len(expected)!=1 or expected[0] in seen:
            raise ValueError('floor_gift_receipt_unknown_repeated_or_pending')
        d['pending']=dict(kind='receipt',title=expected[0],proof=str(proof))
        if title and not same_name(title,expected[0]):d['pending']['printed']=title
        write_json(self.path,d)

    def observe_receipt(self, page, title, proof, *, next_free_offer=None, next_reward_offer=None):
        from .initial_gifts import same_name
        d=self.data;p=d.get('pending')
        if not p or p['kind']!='receipt':raise ValueError('floor_gift_receipt_intent_missing')
        seen=[r['title'] for r in d['receipts']]+[p['title']]
        remaining=[n for n in d['selected'] if n not in seen]
        granted=(title or '').strip() or None
        next_pick=remaining[0] if remaining else None
        next_receipt=(page=='GIFT_GET' and any(same_name(granted,n) for n in remaining))
        # A gift this run already owns cannot be granted twice: the game answers that
        # pick with a different gift printed under its own name (live: the owned
        # 'Portable Battery Socket' came back as 'Faint Vestige').  That notice is the
        # real successor of the pick just confirmed, so it is retained as a labelled
        # observation -- which pick it answers, what the page printed, and whether the
        # pick was a known duplicate -- instead of stopping the run on a name mismatch.
        substituted=(page=='GIFT_GET' and granted is not None and next_pick is not None
            and not same_name(granted,p['title'])
            and not any(same_name(granted,n) for n in remaining))
        free_successor=(not remaining and page=='GIFT_PICK' and next_free_offer
            and next_free_offer.get('count')=={'chosen':0,'required':1}
            and next_free_offer.get('source') in ('single_free_select_button','three_free_select_button')
            and next_free_offer.get('offer'))
        reward_successor=(not remaining and page=='REWARD_CARD' and next_reward_offer
            and next_reward_offer.get('count')=={'chosen':0,'required':1}
            and next_reward_offer.get('title')=='Select Encounter Reward Card')
        final_successor=(not remaining and page in FINAL_SUCCESSOR_PAGES) or bool(free_successor or reward_successor)
        if not (next_receipt or final_successor or substituted):
            raise ValueError('floor_gift_receipt_successor_not_proven')
        label=None
        if substituted:
            label=dict(expected=next_pick,printed=granted,
                       expected_owned=bool((d.get('picked_owned') or {}).get(next_pick)),
                       proof=str(proof))
            d.setdefault('substitutions',[]).append(label)
        record=dict(title=p['title'],receipt=p['proof'],successor=str(proof))
        if p.get('printed'):record['printed']=p['printed']
        d['receipts'].append(record)
        d['completed']=final_successor
        if free_successor:d['next_free_offer']=next_free_offer
        if reward_successor:d['next_reward_offer']=next_reward_offer
        d['pending']=None if final_successor else dict(kind='commit',proof=str(proof))
        if substituted:d['pending']['granted']=granted
        write_json(self.path,d)
        return label


def refusal_confirm_target(record):
    """Exact current question and both controls, independent of background gift."""
    from .vision import Text,find
    records=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
    size=record.get('size') or (1920,1080)
    question=find(records,r'^Continue without choosing an E\.G\.O Gift\?$',(.34,.44,.67,.52),size,.9)
    cancel=find(records,r'^[X×]?\s*Cancel$',(.35,.65,.46,.72),size,.9)
    confirm=find(records,r'^Confirm$',(.55,.65,.66,.72),size,.9)
    if len(question)!=1 or len(cancel)!=1 or len(confirm)!=1:return None
    return list(confirm[0].box)


def retained_notice_name(proof, evidence_root=None):
    """Gift name a retained GIFT_GET proof frame printed, hash-checked.

    Recovery reads what the retained frame actually said; it never re-sends input.
    '' when the frame is present but printed no name.
    """
    from .initial_gifts import receipt_name
    from .vision import Text
    path=Path(proof)
    if evidence_root is not None and not path.resolve().is_relative_to(Path(evidence_root).resolve()):
        raise ValueError('floor_gift_retained_notice_outside_evidence')
    if not path.is_file():raise ValueError('floor_gift_retained_notice_missing')
    record=read_json(path);png=path.with_suffix('.png')
    if record.get('scene')!='GIFT_GET' or not png.is_file():
        raise ValueError('floor_gift_retained_notice_page_not_proven')
    if hashlib.sha256(png.read_bytes()).hexdigest()!=record.get('image_sha256'):
        raise ValueError('floor_gift_retained_notice_image_changed')
    return receipt_name([Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])],
                        record.get('size') or (1920,1080)) or ''


def adopt_legacy_single_pick(transaction, result_path, evidence_root, scope, catalog):
    """Explicit migration of one retained 0→1 input, never automatic recovery.

    Verify the original session's scope, exact target, actual touch, before/after
    frames and hashes. No subsequent input may follow the adopted selection.
    This records an observed selection, never a gift receipt or completed floor.
    """
    from .floor_gifts import observe
    from .vision import Text
    root=Path(evidence_root).resolve(); path=Path(result_path).resolve()
    if transaction.data is not None or not path.is_relative_to(root):
        raise ValueError('floor_gift_legacy_migration_not_allowed')
    result=read_json(path)
    if result.get('run_ledger',{}).get('run')!=scope or not result.get('steps'):
        raise ValueError('floor_gift_legacy_scope_not_proven')
    step=result['steps'][-1]
    if (step.get('page_before')!='GIFT_PICK' or step.get('page_after')!='GIFT_PICK'
        or step.get('reason')!='the_floor_gift_card_must_be_picked_before_select'
        or step.get('clicks_sent')!=1 or not step.get('passed')):
        raise ValueError('floor_gift_legacy_input_not_proven')
    observations=[]; proofs=[]
    for key in ('observation','settled'):
        stored=step[key]; stem=stored['frame']
        if not isinstance(stem,str) or not stem.startswith('frame-') or not stem[6:].isdigit():
            raise ValueError('floor_gift_legacy_frame_invalid')
        frame_path=path.parent/(stem+'.png'); data=read_json(frame_path.with_suffix('.json'))
        digest=hashlib.sha256(frame_path.read_bytes()).hexdigest()
        if digest!=stored['image_sha256'] or digest!=data['image_sha256'] or data['scene']!='GIFT_PICK':
            raise ValueError('floor_gift_legacy_frame_hash_or_scene_mismatch')
        texts=[Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']]
        observations.append(observe(texts,data['size'],catalog));proofs.append(frame_path)
    (before,bcount),(after,acount)=observations
    if bcount!={'chosen':0,'required':acount['required']} or acount['chosen']!=1 or transaction.signature(before)!=transaction.signature(after):
        raise ValueError('floor_gift_legacy_postcondition_not_proven')
    target=tuple(step['plan']['target']); matches=[o for o in before if o.box==target]
    point=step.get('click_point',[])
    if len(matches)!=1 or len(point)!=2 or not (target[0]<=point[0]<=target[0]+target[2] and target[1]<=point[1]<=target[1]+target[3]):
        raise ValueError('floor_gift_legacy_target_not_proven')
    transaction.prepare(scope,before,bcount,proofs[0])
    transaction.intent(matches[0].title,bcount,proofs[0])
    transaction.observe_pick(after,acount,proofs[1])
    transaction.data['legacy_migration']=str(path)
    write_json(transaction.path,transaction.data)
    return transaction.data
