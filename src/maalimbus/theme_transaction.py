"""Persist theme selection intent until an exact successor map proves it."""
from .storage import read_json,write_json
class ThemeTransaction:
    def __init__(self,path):self.path=path;self.data=read_json(path) if path.exists() else dict(pending=None,selected=[])
    def rebase_visible(self,scope):
        """Forget a selection whose floor this launch is being asked to choose again.

        A revived run keeps its scope id, but the floor it is standing on is being offered
        again, so the earlier selection belonged to an attempt that is gone.  A pending drag
        is still refused: that is the one record the game has not answered yet.
        """
        d=self.data
        if not d or d.get('scope')!=scope or d.get('pending'):
            return False
        if not d.get('selected'):
            return False
        d.setdefault('rebased',[]).append(dict(was=d['selected']))
        d['selected']=[]
        write_json(self.path,d)
        return True
    def intent(self,scope,floor,name,proof):
        d=self.data
        if d.get('pending'):raise ValueError('Theme drag remains unverified')
        if not name or not 1<=floor<=5:raise ValueError('Theme floor/name is not proven')
        if d.get('scope')!=scope:d=dict(scope=scope,pending=None,selected=[]);self.data=d
        if any(x['floor']==floor for x in d['selected']):raise ValueError('This floor theme has already been selected')
        d['pending']=dict(floor=floor,name=name,proof=str(proof));write_json(self.path,d)
    def observe(self,scope,header,catalog,proof):
        d=self.data;p=d.get('pending')
        if not p:return False
        if not self.matches(scope,header,catalog):
            raise ValueError('Selected theme successor map floor/name is not proven')
        d['selected'].append(dict(**p,map_proof=str(proof)));d['pending']=None;write_json(self.path,d);return True

    def matches(self,scope,header,catalog):
        """Do the pending selection and the map header name the same pack and floor?

        Both sides are *readings*, so both are resolved through the catalog: the selection
        page can misspell a word and the header can truncate a long title, and neither is a
        different pack (D124).  A side the catalog cannot resolve falls back to comparing
        the raw text, which only ever matches when the two readings agree exactly.
        """
        d=self.data;p=d.get('pending')
        if not p or d.get('scope')!=scope or header is None:
            return False
        if header.floor!=p['floor']:
            return False
        wanted=catalog.identity(p['name']) or p['name']
        seen=catalog.identity(header.pack or '') or (header.pack or '')
        return wanted==seen
