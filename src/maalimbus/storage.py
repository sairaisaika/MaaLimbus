"""Atomic private configuration and durable, ordered run evidence."""
import hashlib
import copy
import json
import os
from dataclasses import asdict
from pathlib import Path
import tempfile
import uuid

from .policies import Team

SINNERS = ('Yi Sang', 'Faust', 'Don Quixote', 'Ryoshu', 'Meursault', 'Hong Lu',
           'Heathcliff', 'Ishmael', 'Rodion', 'Sinclair', 'Outis', 'Gregor')
KEYWORDS = ('Bleed', 'Blunt', 'Burn', 'Charge', 'Keywordless', 'Pierce', 'Poise',
            'Rupture', 'Sinking', 'Slash', 'Tremor', 'Vestige')


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique temporary name and replace protect the previous complete state.
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Configuration/state exceeds 2 MiB')
    return json.loads(path.read_text(encoding='utf-8'))


def team_from_json(value):
    slot = value['slot']
    if type(slot) is not int:
        raise ValueError('Team slot must be an integer')
    deployment = tuple(value.get('deployment', ()))
    if any(s not in SINNERS for s in deployment):
        raise ValueError('Deployment contains an unknown sinner')
    keywords = frozenset(value.get('keywords', ()))
    if not keywords <= set(KEYWORDS):
        raise ValueError('Unknown gift keyword')
    formation_keywords=frozenset(value.get('formation_keywords',()))
    if not formation_keywords<=set(KEYWORDS):raise ValueError('Unknown formation keyword')
    name = value.get('name', '')
    if not isinstance(name, str) or len(name) > 80:
        raise ValueError('Team name must be at most 80 characters')
    return Team(slot, keywords, name, frozenset(value.get('allow', ())),
                frozenset(value.get('block', ())), deployment,
                tuple(tuple(p) for p in value.get('pack_weights', ())), formation_keywords,
                tuple(value.get('graces',())),tuple(value.get('initial_gifts',())),value.get('auto_team',False))


class ProfileStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        value = read_json(self.path)
        if value.get('version') != 1:
            raise ValueError('Unsupported profile version')
        teams = tuple(team_from_json(t) for t in value['teams'])
        if not teams or len(teams) > 20 or len({t.slot for t in teams}) != len(teams):
            raise ValueError('Configure unique saved-team slots in rotation order')
        return teams

    def save(self, teams):
        data = []
        for team in teams:
            value = asdict(team)
            for key in ('keywords', 'allow', 'block', 'formation_keywords'):
                value[key] = sorted(value[key])
            team_from_json(value)
            data.append(value)
        if not data or len(data) > 20 or len({t['slot'] for t in data}) != len(data):
            raise ValueError('Configure unique saved-team slots in rotation order')
        write_json(self.path, {'version': 1, 'teams': data})
        return self.load()


def seed_run_store(path, slots, *, rotation=0):
    """Write a fresh run ledger at a known rotation, before any run is active.

    The rotation order is the player's own (their official ledger), so it is seeded
    explicitly instead of being derived: every slot must be a saved team, and the
    rotation must point at one of them. Refuses to touch an existing file, because
    overwriting a ledger would silently move the player's place in the order.
    """
    path = Path(path)
    slots = [int(s) for s in slots]
    if not slots or len(set(slots)) != len(slots) or any(not 1 <= s <= 20 for s in slots):
        raise ValueError('Configure unique saved-team slots in rotation order')
    if not 0 <= rotation < len(slots):
        raise ValueError('Rotation must point at one of the saved teams')
    if path.exists():
        raise ValueError('A run ledger already exists; do not overwrite it')
    write_json(path, dict(version=1, team_slots=slots, rotation=rotation,
                          completed_runs=0, active=None, receipts=[]))


class RunStore:
    """One active run; rotate exactly once after floor 5, reward and entry return.

    Callers must supply the retained observation file for every transition.
    This stores evidence and order; it does not itself recognize game success.
    """
    def __init__(self, path, teams):
        self.path = Path(path)
        self.slots = [t.slot for t in teams]
        if not self.slots or len(set(self.slots)) != len(self.slots):
            raise ValueError('Invalid rotation')
        if self.path.exists():
            self.data = read_json(self.path)
            if self.data.get('version') != 1 or self.data['team_slots'] != self.slots:
                raise ValueError('Existing run uses another rotation; do not overwrite it')
            if not 0 <= self.data['rotation'] < len(self.slots):
                raise ValueError('Invalid persisted rotation')
        else:
            self.data = dict(version=1, team_slots=self.slots, rotation=0,
                             completed_runs=0, active=None, receipts=[])

    @property
    def team_slot(self):
        return self.slots[self.data['rotation']]

    def start(self):
        if self.data['active'] is None:
            data = copy.deepcopy(self.data)
            data['active'] = dict(id=uuid.uuid4().hex, team=self.team_slot,
                                      floors=[], victory=False, reward=False, events={})
            write_json(self.path, data)
            self.data = data
        return self.data['active']['id']

    def record(self, run_id, event_id, kind, evidence, *, floor=None):
        data = copy.deepcopy(self.data)
        active = data['active']
        if active is None or active['id'] != run_id:
            raise ValueError('Observation does not belong to the active run')
        proof = Path(evidence)
        digest = hashlib.sha256(proof.read_bytes()).hexdigest()
        event = dict(kind=kind, floor=floor, evidence=str(proof.resolve()), sha256=digest)
        if event_id in active['events']:
            if active['events'][event_id] != event:
                raise ValueError('Conflicting observation ID')
            return False
        if kind == 'floor_clear':
            if type(floor) is not int or floor != len(active['floors']) + 1 or not 1 <= floor <= 5:
                raise ValueError('Floors must be verified in sequence')
            active['floors'].append(floor)
        elif kind == 'final_victory':
            if active['floors'] != [1, 2, 3, 4, 5]:
                raise ValueError('Final victory needs all five verified floors')
            active['victory'] = True
        elif kind == 'reward_received':
            if not active['victory']:
                raise ValueError('Reward cannot complete a run without victory')
            active['reward'] = True
        elif kind == 'entry_returned':
            if not active['reward']:
                raise ValueError('Entry return cannot advance an unclaimed run')
        else:
            raise ValueError('Unsupported completion observation')
        active['events'][event_id] = event
        if kind == 'entry_returned':
            data['receipts'].append(active)
            data['receipts'] = data['receipts'][-50:]
            data['completed_runs'] += 1
            data['rotation'] = (data['rotation'] + 1) % len(self.slots)
            data['active'] = None
        write_json(self.path, data)
        self.data = data
        return True
