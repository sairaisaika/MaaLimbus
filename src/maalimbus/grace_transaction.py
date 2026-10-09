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

    def adopt_unspent_entry_settings(self,scope,requested,budget,available,proof):
        """Explicitly repair a zero-budget entry stub before any purchase.

        The caller must bind a current STAR frame and an explicit saved setting.
        This cannot reconfigure a purchase, sealed auto plan or unknown pending.
        """
        d=self.data
        if (not d or d['scope']!=scope or d['budget']!=0 or d['selected'] or
                d['spent']!=0 or d['pending'] is not None or d['available'] is not None or
                'auto_priority' in d or 'entry_settings_adopted' in d):
            raise ValueError('Only an untouched zero-budget entry stub can be adopted')
        if (type(budget) is not int or not 0<=budget<=1000000 or
                type(available) is not int or available<0 or
                not isinstance(requested,list) or len(set(requested))!=len(requested) or
                any(type(n) is not int or not 1<=n<=10 for n in requested)):
            raise ValueError('Explicit entry star choices/budget/current balance required')
        if (not isinstance(proof,dict) or proof.get('page')!='STAR_GRACES' or
                proof.get('scope')!=scope or any(not isinstance(proof.get(k),str) or
                len(proof[k])!=64 for k in ('frame_sha256','configuration_sha256'))):
            raise ValueError('Bound current frame and saved configuration required')
        d['entry_settings_adopted']=dict(previous_requested=list(d['requested']),
            previous_budget=d['budget'],proof=proof)
        d.update(requested=list(requested),budget=budget,available=available)
        write_json(self.path,d)
        return d

    def seal_auto(self,scope,priorities,budget,available,costs,proof):
        """Freeze one affordable plan before input; resumes never re-budget it."""
        d=self.data
        if not d or d['scope']!=scope or d['budget']!=budget or d['pending']:
            raise ValueError('Automatic star scope/budget/pending mismatch')
        if 'auto_priority' in d:
            if d['auto_priority']!=list(priorities):raise ValueError('Automatic star priorities changed')
            if costs is not None and any(costs[n-1]!=d['auto_costs'][str(n)] for n in priorities):
                raise ValueError('Automatic star costs changed')
            return list(d['requested'])
        if costs is None or d['selected'] or d['requested']!=list(priorities):
            raise ValueError('Current auto costs required before selecting stars')
        from .mirror_starlight import affordable
        chosen=affordable(priorities,budget,available,costs)
        d.update(auto_priority=list(priorities),auto_costs={str(n):costs[n-1] for n in priorities},
                 requested=chosen,available=available,auto_plan_proof=str(proof))
        write_json(self.path,d)
        return chosen

    def intent(self,card,cost,available,proof):
        d=self.data
        if (d['pending'] or card not in d['requested'] or card in d['selected'] or cost<=0
                or cost>available or d['spent']+cost>d['budget']
                or ('auto_costs' in d and d['auto_costs'].get(str(card))!=cost)):
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
