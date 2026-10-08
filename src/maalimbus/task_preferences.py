"""Task preferences reference global saved builds; never copy characters into tasks."""
from copy import deepcopy
from .storage import ProfileStore,read_json,write_json

TASKS=('open_game','mirror','experience','thread','rewards','stamina')


class TaskPreferences:
    def __init__(self,directory):
        self.path=directory/'user-task-settings.json'
        self.profiles=ProfileStore(directory/'user-team-profiles.json')

    def validate(self,value):
        if value.get('version')!=1:raise ValueError('Unknown task preferences version')
        builds={p.slot:p for p in self.profiles.load()}
        mirror=value.get('mirror',{})
        if mirror.get('difficulty') not in ('hard','normal'):raise ValueError('Unknown mirror mode')
        queue=mirror.get('teams')
        if (not isinstance(queue,list) or not queue or len(queue)>20 or
                any(type(t) is not int or t not in builds for t in queue) or len(set(queue))!=len(queue)):
            raise ValueError('Mirror queue must reference distinct saved teams')
        if mirror.get('team_mode') not in ('single','rotation'):
            raise ValueError('Unknown mirror team mode')
        if mirror['team_mode']=='single' and len(queue)!=1:
            raise ValueError('Single team mode must reference one saved build')
        lux=value.get('luxcavation',{})
        for name in ('experience_team','thread_team'):
            if type(lux.get(name)) is not int or lux[name] not in builds:
                raise ValueError('Luxcavation default must reference a saved team')
        return value

    def save(self,value):
        self.validate(value)
        write_json(self.path,value)

    def load(self):
        return self.validate(read_json(self.path))

    def build_for(self,task,rotation=0):
        value=self.load()
        if task=='mirror':
            queue=value['mirror']['teams']
            if type(rotation) is not int or rotation<0:raise ValueError('Invalid rotation')
            slot=queue[rotation%len(queue)]
        elif task in ('experience','thread'):
            slot=value['luxcavation'][task+'_team']
        else:raise ValueError('Task does not use a team')
        # Reload the global profile each time. Editing team1 once affects all
        # tasks that reference team1; no stale per-task character duplicates.
        return next(p for p in self.profiles.load() if p.slot==slot)

    def set_lux_defaults(self, **choices):
        if self.path.exists():
            value=deepcopy(self.load())
        else:
            ledger=self.path.parent/'user-run-ledger.json'
            queue=read_json(ledger)['team_slots'] if ledger.exists() else [self.profiles.load()[0].slot]
            value=dict(version=1,mirror=dict(difficulty='hard',team_mode='single' if len(queue)==1 else 'rotation',teams=queue),
                       luxcavation=dict(experience_team=queue[0],thread_team=queue[0]))
        value['luxcavation'].update(choices)
        self.save(value)
        return value

    def set_mirror_queue(self,mode,queue):
        """Explicit idle queue changes retain receipts and the next slot if possible.

        The ledger remains the authority for actual entry. Preference-file failure
        after the ledger write stops the action; no controller input follows it.
        """
        teams=self.profiles.load()
        if self.path.exists():
            value=deepcopy(self.load())
        else:
            default=queue[0] if queue else teams[0].slot
            value=dict(version=1,mirror=dict(difficulty='hard',team_mode=mode,teams=queue),
                       luxcavation=dict(experience_team=default,thread_team=default))
        value['mirror'].update(team_mode=mode,teams=queue)
        self.validate(value)
        ledger_path=self.path.parent/'user-run-ledger.json'
        if ledger_path.exists():
            ledger=read_json(ledger_path)
            old=ledger.get('team_slots')
            rotation=ledger.get('rotation')
            if (ledger.get('version')!=1 or not isinstance(old,list) or not old or
                    type(rotation) is not int or not 0<=rotation<len(old)):
                raise ValueError('Invalid existing ledger; refuse queue change')
            if old!=queue:
                if ledger.get('active') is not None:
                    raise ValueError('Finish the active run before changing its rotation')
                next_slot=old[rotation]
                revised=deepcopy(ledger)
                revised['team_slots']=list(queue)
                revised['rotation']=queue.index(next_slot) if next_slot in queue else 0
                revised.setdefault('queue_changes',[]).append(dict(previous=old,selected=list(queue),
                    previous_rotation=rotation,rotation=revised['rotation'],source='native_mirror_settings'))
                write_json(ledger_path,revised)
        self.save(value)
        return value


def collect_mirror_queue(get_node):
    mode=get_node('MirrorTaskTeamMode')['attach']['team_mode']
    if mode=='saved':return None
    if mode=='single':
        queue=[get_node('MirrorTaskSingleTeam')['attach']['slot']]
    elif mode=='rotation':
        count=get_node('MirrorTaskQueueCount')['attach']['count']
        if type(count) is not int or not 1<=count<=20:raise ValueError('Invalid rotation size')
        queue=[get_node(f'MirrorTaskQueue{n}')['attach']['slot'] for n in range(1,count+1)]
    else:raise ValueError('Unknown mirror team mode')
    return mode,queue
