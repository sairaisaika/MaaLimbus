"""Task preferences reference global saved builds; never copy characters into tasks."""
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
