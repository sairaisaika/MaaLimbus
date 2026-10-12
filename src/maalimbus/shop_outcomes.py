"""Shop policy examples: verified actions and delayed outcomes, never fake strength.

Maa owns perception and input. This Agent-side dataset joins its native evidence
by run scope. A purchased badge labels execution, not a beneficial purchase.
"""
import copy,hashlib,json,shutil
from datetime import datetime
from pathlib import Path
from .storage import read_json,write_json
from .shop_transaction import _verify,_coins,_shelf,_key


def sync(transaction,root,ledger=None):
    data=transaction.data or {};root=Path(root);root.mkdir(parents=True,exist_ok=True)
    run=None
    if ledger:
        state=read_json(ledger)
        if state.get('version')!=1:raise ValueError('Shop outcome ledger version differs')
        runs=[r for r in [state.get('active'),*state.get('receipts',[])]
              if isinstance(r,dict) and r.get('id')==data.get('scope')]
        if len(runs)>1:raise ValueError('Ambiguous shop outcome run')
        run=runs[0] if runs else None
    result=[]
    for receipt in data.get('bought',[]):
        before,btexts,bsize=_verify(receipt['before'])
        after,atexts,asize=_verify(receipt['successor'])
        coins=_coins(btexts,bsize);price=receipt['price']
        prior=_shelf(btexts,bsize);following=_shelf(atexts,asize)
        chosen=[o for o in prior if _key(o['name'])==_key(receipt['name'])]
        kept=[o for o in following if _key(o['name'])==_key(receipt['name'])]
        others=lambda rows:sorted((_key(o['name']),o['price']) for o in rows
                                 if _key(o['name'])!=_key(receipt['name']))
        if (before['scene']!='SHOP' or after['scene']!='SHOP' or len(chosen)!=1
                or chosen[0]['price']!=price or chosen[0].get('purchased')
                or _coins(atexts,asize)!=coins-price or others(prior)!=others(following)
                or kept and (len(kept)!=1 or not kept[0].get('purchased') or kept[0]['price']!=price)):
            raise ValueError('Shop policy purchase evidence differs')
        visit=data['visits'][receipt['visit']]
        payload=dict(version=1,kind='purchase_outcome',scope=data['scope'],visit=receipt['visit'],
            name=receipt['name'],price=price,coins_before=coins,coins_after=coins-price,
            context=copy.deepcopy(receipt.get('decision_context') or visit.get('learning_context')),
            before=receipt['before'],after=receipt['successor'],question=receipt.get('question'),
            receipt_teacher='native_exact_coin_delta_complete_shelf_and_item_status',
            action_executed=True,gift_causal_strength=None)
        key=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest();folder=root/key
        folder.mkdir(exist_ok=True);sample=folder/'sample.json'
        if sample.exists() and read_json(sample)!=payload:raise ValueError('Immutable purchase sample changed')
        if not sample.exists():write_json(sample,payload)
        for role,proof in [('before',receipt['before']),('after',receipt['successor']),
                           ('question',receipt.get('question')),
                           ('notice',(receipt.get('overlay_acknowledgement') or {}).get('frame'))]:
            if not proof:continue
            _verify(proof)
            for suffix,hashfield in [('.json','json_sha256'),('.png','png_sha256')]:
                origin=Path(proof['path']).with_suffix(suffix);target=folder/(role+suffix)
                if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=proof[hashfield]:
                    raise ValueError('Shop policy review bytes changed')
                if not target.exists():shutil.copyfile(origin,target)
        review=folder/'review.json'
        if not review.exists():write_json(review,dict(status='pending',notes='',corrected_category=None))
        outcomes=[]
        if run:
            for event in run.get('events',{}).values():
                if event.get('kind') not in ('floor_clear','final_victory','reward_received','entry_returned'):continue
                path=Path(event['evidence'])
                if hashlib.sha256(path.read_bytes()).hexdigest()!=event['sha256']:
                    raise ValueError('Delayed shop outcome proof changed')
                record=read_json(path);png=path.with_suffix('.png')
                if hashlib.sha256(png.read_bytes()).hexdigest()!=record.get('image_sha256'):
                    raise ValueError('Delayed shop outcome image changed')
                # Earlier floors/old history never become consequences of this purchase.
                if not before.get('utc') or not record.get('utc'):continue
                before_time=datetime.fromisoformat(before['utc']);event_time=datetime.fromisoformat(record['utc'])
                if before_time.tzinfo is None or event_time.tzinfo is None:
                    raise ValueError('Timezone-bound shop outcome required')
                if event_time<=before_time:continue
                for origin,expected in [(path,event['sha256']),(png,record['image_sha256'])]:
                    target=folder/('outcome-'+event['sha256']+origin.suffix)
                    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
                        raise ValueError('Delayed outcome review evidence changed')
                    if not target.exists():shutil.copyfile(origin,target)
                outcomes.append(dict(kind=event['kind'],floor=event.get('floor'),evidence=event,
                    image_sha256=record['image_sha256']))
        label=dict(version=1,category='purchase_completed_outcome_pending' if not outcomes else
                   'purchase_completed_with_later_run_observations',outcomes=outcomes,
                   objective='observed_run_return_not_causal_gift_strength',human_approved=False,
                   training_eligible=False,reason='context_and_independent_episode_quality_review_required')
        write_json(folder/'outcome.json',label)
        (folder/'trace.log').write_text('Scope: '+data['scope']+'\nGift: '+receipt['name']+
            '\nVerified spend: '+str(price)+'\nDelayed outcome count: '+str(len(outcomes))+
            '\nPurchase execution is not purchase value.\n',encoding='utf-8')
        if read_json(review).get('status')!='rejected':result.append(dict(sample=str(sample),**label))
    return result
