"""Preview an audited offline value candidate without authorizing purchase input."""
import hashlib,math
from pathlib import Path
from .storage import read_json


def rank_preview(offers,context,root):
    trace=dict(neural_value_shadow_applied=False,buy_learning_applied=False,
               reason='purchase_value_model_missing_rule_fallback')
    root=Path(root);weights=root/'weights.json';card=root/'modelcard.json'
    if not weights.is_file() or not card.is_file():return list(offers),trace
    try:
        metadata=read_json(card);model=read_json(weights)
        sha=hashlib.sha256(weights.read_bytes()).hexdigest()
        if (metadata.get('weights_sha256')!=sha or metadata.get('synthetic') is not False
                or metadata.get('production_enabled') is not False
                or metadata.get('evidence_verified') is not True
                or type(metadata.get('reviewed_episodes')) is not int
                or metadata['reviewed_episodes']<1 or model.get('schema_version')!=1
                or model.get('production_enabled') is not False):
            raise ValueError('Shop value candidate provenance not verified')
        # The offline encoder is shared; it never supplies input or a policy cap.
        from .shop_value_training import encode_observation,feature_names
        from .shop_value_training import _verification_digest,VERIFICATION_SCHEMA,VERIFICATION_SOURCE
        verification=metadata.get('verification') or {}
        digest=_verification_digest(verification.get('episodes') or [])
        if (verification.get('schema_version')!=VERIFICATION_SCHEMA or verification.get('source')!=VERIFICATION_SOURCE
                or verification.get('verified') is not True
                or verification.get('verified_episodes')!=metadata['reviewed_episodes']
                or digest!=verification.get('dataset_sha256') or digest!=metadata.get('dataset_sha256')
                or digest!=model.get('dataset_sha256')):
            raise ValueError('Shop value dataset manifest differs')
        vocabulary=model['vocabulary'];keywords=model['keyword_vocabulary']
        expected=list(feature_names(vocabulary,keywords))
        if expected!=model['feature_names'] or not 1<=len(expected)<=512:
            raise ValueError('Shop value feature schema differs')
        p=model['parameters'];hidden=model['hidden'];width=len(expected)
        if (type(hidden) is not int or not 1<=hidden<=32 or len(p['w1'])!=hidden
                or len(p['b1'])!=hidden or len(p['w2'])!=hidden
                or any(len(row)!=width for row in p['w1'])):
            raise ValueError('Shop value network shape differs')
        values=[p['b2'],*p['b1'],*p['w2'],*[x for row in p['w1'] for x in row]]
        if any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>100 for x in values):
            raise ValueError('Shop value network contains invalid weights')
        scores=[]
        for offer in offers:
            observation=dict(context,action='buy',offer_name=offer.name,price=offer.price)
            vector=encode_observation(observation,vocabulary=vocabulary,keyword_vocabulary=keywords)['values']
            activated=[math.tanh(sum(a*b for a,b in zip(row,vector))+bias)
                       for row,bias in zip(p['w1'],p['b1'])]
            logit=sum(a*b for a,b in zip(activated,p['w2']))+p['b2']
            score=1/(1+math.exp(-max(-60,min(60,logit))))
            scores.append(dict(name=offer.name,predicted_review_value=score))
        ranked=metadata.get('participation')=='ranked'
        if ranked:
            order=sorted(range(len(offers)),key=lambda index:(-scores[index]['predicted_review_value'],index))
            ordered=[offers[index] for index in order]
        else:
            ordered=list(offers)
        return ordered,dict(trace,neural_value_shadow_applied=True,neural_value_ranked=ranked,
            participation=metadata.get('participation'),reviewed_episodes=metadata.get('reviewed_episodes'),
            held_out=(metadata.get('curriculum') or {}),model_sha256=sha,scores=scores,
            reason=('candidate_promoted_by_its_own_held_out_ordering_within_the_plans_offers' if ranked
                    else 'candidate_shadow_only_not_a_promoted_purchase_policy'))
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as error:
        return list(offers),dict(trace,reason='invalid_value_candidate_rule_fallback',diagnostic=str(error))
