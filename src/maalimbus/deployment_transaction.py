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
            d=dict(scope=scope,order=list(order),saved_order=saved_order,unavailable=unavailable,
                   availability_proof=availability_proof,sequence=[],pending=None,submitted=False);self.data=d;write_json(self.path,d)
        if d['order']==saved_order and d['order']!=order and not d['sequence'] and count[0]==0:
            d.update(saved_order=saved_order,order=order,unavailable=unavailable,availability_proof=availability_proof)
            write_json(self.path,d)
        if d['order']!=list(order):raise ValueError('Deployment order changed during selection')
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
