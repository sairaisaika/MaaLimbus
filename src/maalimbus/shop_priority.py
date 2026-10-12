"""Explicit player priorities, separate from learned estimates and gift effects."""
from .storage import read_json


def load(path,catalog):
    if not path.exists():return {}
    data=read_json(path)
    if data.get('version')!=1 or not isinstance(data.get('priorities'),list):
        raise ValueError('Invalid shop priority settings')
    answer={}
    for entry in data['priorities']:
        if not isinstance(entry,dict):raise ValueError('Invalid shop priority entry')
        name,weight=entry.get('name'),entry.get('weight')
        if (name not in catalog.entries or name in answer or type(weight) is not int
                or not 0<=weight<=100):raise ValueError('Known unique gift and integer priority 0..100 required')
        answer[name]=weight
    return answer
