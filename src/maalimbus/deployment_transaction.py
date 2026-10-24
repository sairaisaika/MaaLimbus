"""Reuse the visible saved order; change only a proven different order."""
from .storage import read_json,write_json
class DeploymentTransaction:
    def __init__(self,path):self.path=path;self.data=read_json(path) if path.exists() else None
    def prepare(self,scope,order,count,numbers=None,unavailable=(),availability_proof=None):
        """What the page needs next: clear it, keep picking, or submit.

        The game keeps the previous encounter's deployment, so a page that already
        prints the saved order position on every card needs no clear at all -- the
        driver submits it (`numbers` is `team_vision.assignment_numbers` output).
        """
        saved_order=list(order)
        unavailable=list(unavailable)
        if unavailable and (not availability_proof or not availability_proof.get('accepted')
                or availability_proof.get('unavailable')!=unavailable
                or len(set(unavailable))!=len(unavailable) or any(i not in saved_order for i in unavailable)
                or count[1]!=len(saved_order)-len(unavailable)):
            raise ValueError('Unavailable deployment cards not independently proven')
        order=[i for i in saved_order if i not in unavailable]
        if count[1]!=len(order):raise ValueError('Current deployment capacity requires independent unavailable-card proof')
        d=self.data
        if d and (d.get('pending') or d.get('submit_pending')):raise ValueError('Unverified deployment input remains pending')
        if not d or d['scope']!=scope or d.get('submitted'):
            # A revive receipt is money the shop's own counter already took, so it outlives the
            # rewrite that clears the selection -- otherwise the next shop visit of the same run
            # reads a dead slot again and walks back into the picker it has already paid for.  The
            # in-run currency is spent per run, so a frame naming another scope inherits nothing.
            receipts=[row for row in d.get('revives') or ()] if d and d['scope']==scope else []
            d=dict(scope=scope,order=list(order),saved_order=saved_order,unavailable=unavailable,
                   availability_proof=availability_proof,sequence=[],pending=None,submitted=False,
                   revives=receipts);self.data=d;write_json(self.path,d)
        if d['order']==saved_order and d['order']!=order and not d['sequence'] and count[0]==0:
            d.update(saved_order=saved_order,order=order,unavailable=unavailable,availability_proof=availability_proof)
            write_json(self.path,d)
        if d['order']!=list(order):
            # A board that names another team changes the order before anything was
            # clicked: nothing has been reserved for the old order, so re-pointing the
            # card does not lose a transaction (D119 -- the pre-battle page can now be
            # adopted from the screen, and the rotation's order would otherwise stop the
            # run with 'Deployment order changed during selection').
            if not d.get('sequence') and not d.get('pending') and not d.get('submitted'):
                d.update(order=list(order), unavailable=list(unavailable))
                write_json(self.path,d)
            else:
                raise ValueError('Deployment order changed during selection')
        if d['sequence'] and count[0]!=len(d['sequence']):raise ValueError('Participant count diverged from verified deployment')
        from .team_vision import carries_saved_order
        inherited=carries_saved_order(numbers,order,count)
        expected={card:position for position,card in enumerate(order[:count[0]],1)}
        contradicted=bool(numbers and any(value is not None and expected.get(card)!=value
                            for card,value in enumerate(numbers,1)))
        uncertain=not d['sequence'] and count[0]>0 and not inherited and not contradicted
        return dict(reset_required=not d['sequence'] and count[0]>0 and not inherited and contradicted,
                    order_verified=(d['sequence']==list(order)[:count[1]] and count[0]==count[1]) or inherited,
                    inherited_order=inherited,assignment=numbers,order_uncertain=uncertain,
                    order=list(order),unavailable=unavailable)
    def reconcile_unavailable(self,scope,count,unavailable,proof):
        """Archive a proven no-op on a dead card, without counting it as selected."""
        d=self.data;p=d.get('pending') if d else None
        if not (d and d['scope']==scope and p and p['kind']=='card'
                and p['card'] in unavailable and count==(p['before'],p['capacity'])
                and proof and proof.get('accepted') and proof.get('image_sha256') and proof.get('frame')
                and proof.get('unavailable')==list(unavailable) and proof.get('participants')==list(count)
                and count[1]==12-len(set(unavailable))):
            raise ValueError('Pending unavailable card no-op not proven')
        d.setdefault('rejected_unavailable_inputs',[]).append(dict(intent=dict(p),proof=proof,
                                                               selected=False,recovery_input=False))
        d['pending']=None;write_json(self.path,d)
    def retire_foreign(self,scope,reason=None,*,force=False):
        """Drop a card another run reserved, and keep the fact that it was given up.

        A pending card is only cleared by `observe`, which needs the party count of the
        battle that run submitted.  A run that ended first leaves the card in the ledger
        and the next run inherits a reservation it can never observe: measured on
        `evidence/runtime/packaged-mirror-20261024-061628`, a fresh run read
        `Deployment_transaction.pending` for 180 s, sent no click at all, and ended on
        `the_submitted_turn_never_showed_a_page`.  Retiring it is not spending: no
        currency, no input, and the abandonment is written where the ledger keeps its
        other evidence.
        """
        d=self.data or {}
        pending=d.get('pending')
        if not pending:
            return None
        # `force` is the run-start door: a fresh run has reserved nothing yet, so any
        # card in the ledger was written by a run that is over.  Measured on
        # `packaged-mirror-20261024-062803`: the card was still there, its scope was a
        # previous run's id, and the loop spent its whole window waiting on it.
        if not force and d.get('scope')==scope:
            return None
        d.setdefault('abandoned',[]).append(dict(intent=dict(pending),scope=d.get('scope'),
                                                 reason=reason))
        d['pending']=None
        write_json(self.path,d)
        return dict(scope=d.get('scope'),kind=pending.get('kind'),reason=reason)

    def intent(self,kind,count,card=None):
        d=self.data
        if d['pending']:raise ValueError('Deployment input already pending')
        if kind=='card' and card!=d['order'][len(d['sequence'])]:raise ValueError('Deployment click violates saved order')
        d['pending']=dict(kind=kind,before=count[0],capacity=count[1],card=card);write_json(self.path,d)
    def observe(self,count):
        d=self.data;p=d['pending'];want=0 if p['kind']=='clear' else p['before']+1
        if count!=(want,p['capacity']):raise ValueError('Deployment successor participant count not proven')
        if p['kind']=='clear':d['sequence']=[]
        else:d['sequence'].append(p['card'])
        d['pending']=None;write_json(self.path,d)
    def confirm_clear(self,scope):
        d=self.data;p=d.get('pending') if d else None
        if not d or d['scope']!=scope or not p or p['kind']!='clear' or p.get('confirm_sent'):
            raise ValueError('Deployment reset confirmation is not authorized by pending clear')
        p['confirm_sent']=True;write_json(self.path,d)
    def revived_cards(self):
        """The deck cards a booked revive brought back, read from its own receipts."""
        return sorted({row['card'] for row in (self.data or {}).get('revives') or ()
                       if isinstance(row,dict) and isinstance(row.get('card'),int)})
    def book_revive(self,card,cost,coins_before,coins_after,proof=None):
        """Record a revive whose price is the currency delta the shop's own counter shows.

        The shop's Heal Sinner service is paid for out of the run's in-run currency, so the
        only receipt that proves it happened is the shop's counter moving by exactly the
        price its modal printed (live 2026-10-12: 3093 -> 2993 for Hong Lu's 100).  Any
        other delta is refused instead of booked: a revive the run cannot prove would let
        the next shop visit believe a dead slot is still fieldable.
        """
        d=self.data
        if not d:raise ValueError('No deployment store to book a revive against')
        if not isinstance(card,int) or not 1<=card<=12:
            raise ValueError('Revive receipt names no deck card')
        if not isinstance(cost,int) or cost<=0 or not isinstance(coins_before,int) \
                or not isinstance(coins_after,int) or coins_before-coins_after!=cost:
            raise ValueError('Revive receipt does not match the price the modal printed')
        d.setdefault('revives',[]).append(dict(card=card,cost=cost,coins_before=coins_before,
                                               coins_after=coins_after,proof=proof))
        write_json(self.path,d)
        return True
