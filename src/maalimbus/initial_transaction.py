"""Scoped initial gift choices with retained title/counter/row evidence."""
from .storage import read_json,write_json
class InitialTransaction:
    def __init__(self,path):
        self.path=path;self.data=read_json(path) if path.exists() else None
    def prepare(self,scope,keyword,count,proof):
        d=self.data
        if not d or d['scope']!=scope:
            if d and d['pending']:raise ValueError('Unverified initial gift remains pending')
            if count[0]!=0:raise ValueError('Initial choices have no scoped proof')
            d=dict(scope=scope,keyword=keyword,selected=[],pending=None,proofs=[str(proof)])
            self.data=d;write_json(self.path,d)
        if d['pending'] or count[0]!=len(d['selected']):
            raise ValueError('Initial gift scope, keyword, pending or counter mismatch')
        if d['keyword']!=keyword:
            # The keyword is a purchase *preference*, not a promise: a resumed scope may
            # legitimately carry a different one once the team or its systems change
            # (`charge` -> `charge+tremor` did exactly that).  A pending gift and a
            # disagreeing counter are still refusals, because those are promises.
            d.setdefault('keyword_history',[]).append(d['keyword'])
            d['keyword']=keyword
            write_json(self.path,d)
        return d
    def rebase_visible(self,scope,count,proof):
        """Adopt the counter the page shows when a revived scope's record is stale.

        A resumed run reuses its scope id but the client's counter belongs to the attempt
        that is on screen now, so the recorded `selected` rows cannot be proven any more.
        They are kept as history and the counter is adopted; an unverified pending gift is
        still refused, because that is the one case the record is a promise.
        """
        d=self.data
        if not d or d['scope']!=scope or d.get('pending'):
            return False
        if count[0]==len(d.get('selected') or []):
            return False
        d.setdefault('rebased',[]).append(dict(was=d.get('selected'),
                                              counter=list(count),proof=str(proof)))
        d['selected']=[]
        write_json(self.path,d)
        return True
    def intent(self,row,title,count,proof):
        d=self.data
        if d['pending'] or any(x['title']==title for x in d['selected']):
            raise ValueError('Initial gift would repeat an unverified or selected row')
        d['pending']=dict(row=row,title=title,before=count[0],capacity=count[1],proof=str(proof))
        write_json(self.path,d)
    def observe(self,count,rows,proof):
        d=self.data;p=d['pending']
        if not p or count!=(p['before']+1,p['capacity']) or p['row'] not in (rows or []):
            raise ValueError('Initial gift selected count and row not proven')
        d['selected'].append(dict(row=p['row'],title=p['title']))
        d['proofs'].append(str(proof));d['pending']=None;write_json(self.path,d)
