"""Do not inherit a previous encounter's participant order."""
from .storage import read_json,write_json
class DeploymentTransaction:
    def __init__(self,path):self.path=path;self.data=read_json(path) if path.exists() else None
    def prepare(self,scope,order,count):
        d=self.data
        if d and (d.get('pending') or d.get('submit_pending')):raise ValueError('Unverified deployment input remains pending')
        if not d or d['scope']!=scope or d.get('submitted'):
            d=dict(scope=scope,order=list(order),sequence=[],pending=None,submitted=False);self.data=d;write_json(self.path,d)
        if d['order']!=list(order):raise ValueError('Deployment order changed during selection')
        if d['sequence'] and count[0]!=len(d['sequence']):raise ValueError('Participant count diverged from verified deployment')
        return dict(reset_required=not d['sequence'] and count[0]>0,
                    order_verified=d['sequence']==list(order)[:count[1]] and count[0]==count[1])
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
