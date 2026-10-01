import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_mxu_deployment_replay import resolve_choices


def task(preset):
    options={'team_slot':{'type':'select','caseName':'2'},
             'deployment_preset':{'type':'select','caseName':preset}}
    if preset=='custom':
        options.update({f'deployment_position_{i}':{'type':'select','caseName':str(3 if i==1 else 1 if i==3 else i)}
                        for i in range(1,13)})
    return {'taskName':'prepare_deployment','optionValues':options}


def test_actual_pi_custom_choices_keep_independent_node_parameters():
    interface=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    patches=resolve_choices(interface,task('custom'))
    assert patches['DeploymentConfigure']['custom_action_param']=={'mode':'configure','slot':2}
    assert patches['DeploymentOrder1']['custom_action_param']['sinner']=='Don Quixote'
    assert patches['DeploymentOrder3']['custom_action_param']['sinner']=='Yi Sang'
    assert len([n for n in patches if n.startswith('DeploymentOrder')])==12


def test_inactive_custom_children_are_not_resolved():
    interface=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    patches=resolve_choices(interface,task('saved'))
    assert not any(n.startswith('DeploymentOrder') for n in patches)


def test_unknown_saved_selection_is_rejected_before_creating_any_controller():
    interface=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    current=task('custom');current['optionValues']['deployment_position_1']['caseName']='Unknown'
    with pytest.raises(StopIteration):resolve_choices(interface,current)
