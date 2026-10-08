"""Durable base-grace purchases; unverified input is never retried."""
from .storage import read_json, write_json


class GraceTransaction:
    def __init__(self,path):
        self.path=path
        self.data=read_json(path) if path.exists() else None

    def begin(self,scope,requested,budget,proof):
        if self.data and self.data.get('pending'):
            raise ValueError('Unverified grace purchase remains pending')
        self.data=dict(scope=scope,requested=list(requested),budget=budget,selected=[],
                       spent=0,available=None,pending=None,proofs=[str(proof)])
        write_json(self.path,self.data)

    def validate(self,scope,requested,budget,available):
        d=self.data
        if not d or d['scope']!=scope or d['requested']!=list(requested) or d['budget']!=budget:
            raise ValueError('Grace transaction scope or configuration mismatch')
        if d['pending']:raise ValueError('Unverified grace purchase remains pending')
        if d['available'] is not None and available!=d['available']:
            raise ValueError('Grace balance changed outside verified purchases')
        return d

    def intent(self,card,cost,available,proof):
        d=self.data
        if d['pending'] or card in d['selected'] or cost<=0 or cost>available or d['spent']+cost>d['budget']:
            raise ValueError('Grace purchase is not authorized by this transaction')
        d['pending']=dict(card=card,cost=cost,before=available,proof=str(proof))
        write_json(self.path,d)

    def observe(self,available,proof):
        d=self.data;p=d['pending']
        if not p or available!=p['before']-p['cost']:
            raise ValueError('Grace purchase successor balance not proven')
        d['selected'].append(p['card']);d['spent']+=p['cost'];d['available']=available
        d['proofs'].append(str(proof));d['pending']=None
        write_json(self.path,d)
