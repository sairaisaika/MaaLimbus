import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_mxu_deployment_replay import resolve_choices


def task(mode):
    options={'mirror_team_mode':{'type':'select','caseName':mode},
             'mirror_star_source':{'type':'select','caseName':'saved'},
             'mirror_single_team':{'type':'select','caseName':'7'},
             'mirror_queue_count':{'type':'select','caseName':'5'}}
    options.update({f'mirror_queue_{i}':{'type':'select','caseName':str(i)} for i in range(1,21)})
    options.update({name:{'type':'select','caseName':'saved'} for name in
                    ('mirror_initial_keyword','mirror_gift_search','mirror_run_bounds','mirror_preferences')})
    return {'taskName':'mirror_loop','optionValues':options}


def test_actual_pi_queue_choices_keep_independent_node_parameters():
    interface=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    patches=resolve_choices(interface,task('rotation'))
    assert patches['MirrorTaskTeamMode']['attach']['team_mode']=='rotation'
    assert patches['MirrorTaskQueueCount']['attach']['count']==5
    assert patches['MirrorTaskQueue1']['attach']['slot']==1
    assert patches['MirrorTaskQueue3']['attach']['slot']==3
    assert len([n for n in patches if n.startswith('MirrorTaskQueue')])==6


def test_inactive_rotation_children_are_not_resolved():
    interface=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    patches=resolve_choices(interface,task('single'))
    assert patches['MirrorTaskSingleTeam']['attach']['slot']==7
    assert not any(n.startswith('MirrorTaskQueue') for n in patches)


def test_unknown_saved_selection_is_rejected_before_creating_any_controller():
    interface=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    current=task('single');current['optionValues']['mirror_single_team']['caseName']='Unknown'
    with pytest.raises(ValueError,match='Unknown'):resolve_choices(interface,current)
    current['taskName']='prepare_deployment'
    with pytest.raises(ValueError,match='no longer exists'):resolve_choices(interface,current)
