"""Learn observed shelf yield from native receipts; never invent gift strength.

This is an empirical decision layer, not a neural perception model. Only verified
coin deltas and complete shelves teach refresh yield. Unknown receipts do not
become failures or training data. Player caps and allowed names are applied first.
"""
import hashlib
import json
import shutil
from pathlib import Path
from .storage import read_json,write_json
from .shop_transaction import _verify,_coins,_shelf,_key


def _fingerprint(rows):
    return sorted((_key(o['name']),o['price']) for o in rows)


def sync_receipts(transaction,root,wanted,keywords):
    """Reaudit retained transactions, copy one review bundle per real receipt.

    Returns only verified, non-rejected samples for this keyword context. Names
    are reconciled against the caller's allowed list, never added to that list.
    Repeated GUI starts cannot duplicate a sample.
    """
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    allowed={_key(n) for n in wanted};context=sorted(keywords)
    data=transaction.data or {}
    for visit_id,visit in data.get('visits',{}).items():
        for receipt in visit.get('refresh_receipts',[]):
            before,btexts,bsize=_verify(receipt['before'])
            after,atexts,asize=_verify(receipt['successor'])
            a,b=_shelf(atexts,asize),_shelf(btexts,bsize)
            cost=receipt['price'];coins=_coins(btexts,bsize)
            if (type(cost) is not int or cost<=0 or before['scene']!='SHOP'
                    or after['scene']!='SHOP' or _coins(atexts,asize)!=coins-cost
                    or not a or len(a)!=len(b) or _fingerprint(a)==_fingerprint(b)):
                raise ValueError('Shop learning refresh proof differs')
            # The original visit's saved-team keyword context is required; a
            # later profile edit cannot retroactively label an earlier action.
            captured=visit.get('learning_context')
            if (not captured or captured.get('keywords')!=context
                    or captured.get('wanted')!=sorted(wanted)):continue
            old={_key(o['name']) for o in b}
            useful=[o['name'] for o in a if _key(o['name']) in allowed
                    and _key(o['name']) not in old and o['price'] is not None
                    and o['price']<=coins-cost-captured['reserve_coins']]
            payload=dict(version=1,kind='regular_refresh',scope=data['scope'],visit=visit_id,
                context=captured,price=cost,coins_before=coins,new_affordable_wanted=useful,
                useful_yield=len(useful),teacher='native_complete_shelves_exact_coin_delta',
                before=receipt['before'],after=receipt['successor'],
                gift_causal_strength=None,neural_model_trained=False)
            key=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
            folder=root/key;folder.mkdir(exist_ok=True)
            destination=folder/'sample.json'
            if destination.exists() and read_json(destination)!=payload:
                raise ValueError('Immutable shop learning sample changed')
            if not destination.exists():write_json(destination,payload)
            for role in ('before','after'):
                original=Path(payload[role]['path'])
                for suffix in ('.json','.png'):
                    source=original.with_suffix(suffix);target=folder/(role+suffix)
                    expected=payload[role]['json_sha256' if suffix=='.json' else 'png_sha256']
                    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
                        raise ValueError('Shop review evidence changed')
                    if not target.exists():shutil.copyfile(source,target)
            review=folder/'review.json'
            if not review.exists():write_json(review,dict(status='pending',notes='',corrected_category=None))
            proposal=folder/'proposal.json'
            if not proposal.exists():write_json(proposal,dict(category='refresh_added_wanted_affordable' if useful
                else 'refresh_no_new_wanted_affordable',sample_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                human_approved=False,perception_training_eligible=False))
            (folder/'trace.log').write_text('Observed refresh yield: '+str(len(useful))+
                '\nCost: '+str(cost)+'\nScope: '+data['scope']+'\n',encoding='utf-8')
    result=[]
    for file in sorted(root.glob('*/sample.json')):
        if read_json(file.parent/'review.json').get('status')=='rejected':continue
        sample=read_json(file)
        if (sample.get('version')!=1 or sample.get('context',{}).get('keywords')!=context
                or sample.get('context',{}).get('wanted')!=sorted(wanted)):continue
        if hashlib.sha256(json.dumps(sample,sort_keys=True).encode()).hexdigest()!=file.parent.name:
            raise ValueError('Shop sample content address differs')
        # Revalidate underlying sources on every use, not merely once at training.
        _,btexts,bsize=_verify(sample['before']);_,atexts,asize=_verify(sample['after'])
        a,b=_shelf(atexts,asize),_shelf(btexts,bsize);coins=_coins(btexts,bsize)
        useful=[o['name'] for o in a if _key(o['name']) in allowed
            and _key(o['name']) not in {_key(o['name']) for o in b}
            and o['price'] is not None and o['price']<=coins-sample['price']-sample['context']['reserve_coins']]
        if (_coins(atexts,asize)!=coins-sample['price'] or not a or len(a)!=len(b)
                or _fingerprint(a)==_fingerprint(b) or len(useful)!=sample.get('useful_yield')):
            raise ValueError('Persisted shop yield differs from its native evidence')
        result.append(sample)
    return result


def rank_offers(offers,samples,context=None):
    """No survival/strength evidence yet: deterministic affordable rule fallback."""
    # Buying receipt != stronger party. Never train strength from transaction success.
    from .runtime_paths import ROOT
    from .shop_value_shadow import rank_preview
    ordered,trace=rank_preview(offers,context or {},ROOT/'assets/resource/base/model/shop-value')
    return ordered,dict(trace,mode='learned',samples=len(samples))


def refresh_decision(samples,trace=None):
    """Stop low-yield refreshes early after independent visits show no wanted stock.

    Missing evidence preserves bounded rule exploration. It can only reduce
    spending, never create an input or raise a cap. No claim of causal optimality.
    """
    episodes={(s['scope'],s['visit']) for s in samples}
    trace=dict(trace or {},refresh_samples=len(samples),independent_visits=len(episodes),
               refresh_learning_applied=False)
    if len(episodes)<3:
        return True,dict(trace,refresh_reason='insufficient_independent_visits_rule_fallback')
    rate=sum(s['useful_yield']>0 for s in samples)/len(samples)
    if rate==0:
        return False,dict(trace,refresh_learning_applied=True,observed_yield_rate=rate,
                          refresh_reason='three_verified_visits_without_new_wanted_stock')
    return True,dict(trace,observed_yield_rate=rate,refresh_reason='observed_stock_yield_within_player_caps')
