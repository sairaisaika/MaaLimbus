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
        if d['keyword']!=keyword or d['pending'] or count[0]!=len(d['selected']):
            raise ValueError('Initial gift scope, keyword, pending or counter mismatch')
        return d
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
