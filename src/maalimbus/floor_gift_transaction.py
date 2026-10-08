"""Durable floor gift intents. Unknown postconditions never permit another input."""
import hashlib
import json
from pathlib import Path

from .storage import read_json, write_json


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
                     selected=[],pending=None,commit_sent=False,receipts=[],
                     completed=False,proofs=[str(proof)],history=history)
            self.data=d
            write_json(self.path,d)
        if d['pending'] or d['commit_sent'] or d['completed'] or count['required']!=d['required'] or count['chosen']!=len(d['selected']):
            raise ValueError('floor_gift_pending_commit_or_counter_mismatch')
        return d

    def intent(self, title, count, proof):
        d=self.data
        if d['pending'] or d['commit_sent'] or title in d['selected'] or count['chosen']!=len(d['selected']):
            raise ValueError('floor_gift_selection_would_repeat')
        d['pending']=dict(kind='pick',title=title,before=count['chosen'],proof=str(proof))
        write_json(self.path,d)

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

    def receipt_intent(self, title, proof):
        from .initial_gifts import same_name
        d=self.data;p=d.get('pending')
        expected=[n for n in d['selected'] if same_name(n,title)]
        seen=[r['title'] for r in d['receipts']]
        if not d['commit_sent'] or not p or p['kind']!='commit' or len(expected)!=1 or expected[0] in seen:
            raise ValueError('floor_gift_receipt_unknown_repeated_or_pending')
        d['pending']=dict(kind='receipt',title=expected[0],proof=str(proof))
        write_json(self.path,d)

    def observe_receipt(self, page, title, proof):
        from .initial_gifts import same_name
        d=self.data;p=d.get('pending')
        if not p or p['kind']!='receipt':raise ValueError('floor_gift_receipt_intent_missing')
        seen=[r['title'] for r in d['receipts']]+[p['title']]
        remaining=[n for n in d['selected'] if n not in seen]
        next_receipt=(page=='GIFT_GET' and any(same_name(title,n) for n in remaining))
        final_successor=(not remaining and page in ('THEME_PACKS','MAP'))
        if not (next_receipt or final_successor):
            raise ValueError('floor_gift_receipt_successor_not_proven')
        d['receipts'].append(dict(title=p['title'],receipt=p['proof'],successor=str(proof)))
        d['completed']=final_successor
        d['pending']=None if final_successor else dict(kind='commit',proof=str(proof))
        write_json(self.path,d)


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
