"""Durable paid-claim intents; receipt recognition is deliberately not inferred.

The caller must independently prove currency and current cost. Balances hidden
on the reward page remain explicitly unknown rather than guessed from summaries.
Unknown pending intents cannot be
retried, replaced, or treated as a payout, even with a larger later budget.
"""
import copy
import re
from .storage import read_json,write_json


class RewardClaimTransaction:
    def __init__(self,path):
        self.path=path
        self.data=read_json(path) if path.exists() else None

    def reserve(self,scope,policy,offer,balances,proof):
        history=[]
        if self.data is not None:
            old=self.data
            chain=old.get('receipt_chain')
            history=old.get('history',[])
            if (old.get('scope')==scope or old.get('completed') is not True
                or old.get('reward_received') is not True or old.get('pending') is not None
                or not all(old.get(k) for k in ('claim_sent','confirm_sent','receipt_ack_sent',
                    'claim_proof','confirm_proof','receipt_proof','home_return_proof'))
                or not isinstance(chain,list) or len(chain)<2
                or any(not isinstance(p,dict) or not p.get('frame') or
                    not re.fullmatch(r'[0-9a-f]{64}',str(p.get('png_sha256',''))) for p in chain)
                or old['home_return_proof']!=chain[-1]['frame']
                or not isinstance(history,list)
                or any(not isinstance(p,dict) or p.get('scope')==scope for p in history)):
                raise ValueError('reward_claim_existing_transaction_requires_reconciliation')
            archived=copy.deepcopy(old)
            archived.pop('history',None)
            history=copy.deepcopy(history)+[archived]
        maximum=policy.get('max_reward_modules')
        if (policy.get('module_budget_pending',True) or type(maximum) is not int
            or maximum<=0 or policy.get('reward_budget_scope')!=scope):
            raise ValueError('reward_claim_scoped_budget_missing')
        cost=offer.get('cost');weekly=offer.get('weekly')
        if (offer.get('currency')!='enkephalin_modules' or type(cost) is not int
            or cost<=0 or type(weekly) is not int or not 0<=weekly<=3):
            raise ValueError('reward_claim_cost_or_currency_unknown')
        if cost>maximum:raise ValueError('reward_claim_over_budget')
        hidden_modules=(balances.get('modules') is None and
            balances.get('module_visibility')=='not_displayed_on_reward_page')
        hidden_stars=(balances.get('starlight') is None and
            balances.get('starlight_visibility')=='not_displayed_on_reward_page')
        if ((not hidden_modules and (type(balances.get('modules')) is not int or balances['modules']<cost))
            or (not hidden_stars and (type(balances.get('starlight')) is not int or balances['starlight']<0))):
            raise ValueError('reward_claim_before_balances_missing')
        if not scope or not proof:raise ValueError('reward_claim_proof_missing')
        data=dict(scope=scope,maximum_modules=maximum,reserved_modules=cost,
            offer=dict(offer),before_balances=dict(balances),proof=str(proof),
            claim_sent=False,confirm_sent=False,completed=False,pending='reserved',
            reward_received=False)
        if history:data['history']=history
        write_json(self.path,data)
        self.data=data
        return self.data

    def claim_intent(self,scope,offer,proof):
        d=self.data
        if (not d or d['scope']!=scope or d['pending']!='reserved'
            or d['claim_sent'] or offer!=d['offer'] or not proof):
            raise ValueError('reward_claim_input_unproven_or_repeated')
        d.update(claim_sent=True,pending='claim',claim_proof=str(proof))
        write_json(self.path,d)

    def confirm_intent(self,scope,proof,*,question_proven=False):
        d=self.data
        if (not d or d['scope']!=scope or d['pending']!='claim'
            or not d['claim_sent'] or d['confirm_sent'] or not question_proven or not proof):
            raise ValueError('reward_claim_confirmation_unproven_or_repeated')
        d.update(confirm_sent=True,pending='confirm',confirm_proof=str(proof))
        write_json(self.path,d)
