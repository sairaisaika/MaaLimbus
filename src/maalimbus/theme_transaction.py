"""Persist theme selection intent until an exact successor map proves it."""
from .storage import read_json,write_json
class ThemeTransaction:
    def __init__(self,path):self.path=path;self.data=read_json(path) if path.exists() else dict(pending=None,selected=[])
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
        d=self.data;p=d.get('pending')
        return bool(p and d.get('scope')==scope and header is not None
                    and header.floor==p['floor'] and catalog.identity(header.pack or '')==p['name'])
