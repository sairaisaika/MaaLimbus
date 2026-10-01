"""PI options must not replace another option's custom_action_param object."""
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def test_independent_option_nodes_and_complete_custom_parameters():
    interface=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    nodes=json.loads((ROOT/'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf-8'))
    changed={}
    for option in ('team_slot','team_name','pack_name','pack_weight'):
        definition=interface['option'][option]
        patches=[c['pipeline_override'] for c in definition['cases']] if 'cases' in definition else [definition['pipeline_override']]
        names=set()
        for patch in patches:
            for node,value in patch.items():
                assert node in nodes
                assert value['custom_action_param']['mode'] in ('configure','name','pack','weight')
                names.add(node)
        changed[option]=names
    assert changed['team_slot'].isdisjoint(changed['pack_name']|changed['pack_weight']|changed['team_name'])
    assert changed['pack_name'].isdisjoint(changed['pack_weight'])
    tasks={t['entry']:t for t in interface['task']}
    assert not tasks['ThemePackStart']['default_check']
    assert nodes['ThemePackDrag']['max_hit']==1
    assert nodes['ThemePackBoundary']['custom_action_param']['reason']=='theme_drag_recorded_map_verification_pending'


def test_deployment_requires_saved_order_or_explicit_preset_and_is_bounded():
    interface=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    nodes=json.loads((ROOT/'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf-8'))
    preset=interface['option']['deployment_preset']
    assert preset['default_case']=='saved'
    assert not next(t for t in interface['task'] if t['entry']=='DeploymentStart')['default_check']
    assert nodes['DeploymentNext']['max_hit']==12
    assert nodes['DeploymentComplete']['custom_action']=='limbus_deployment_proof'
    assert nodes['DeploymentBoundary']['custom_action_param']['reason']=='deployment_order_observed_battle_not_started'
    assert {name for case in preset['cases'] for name in case['pipeline_override']}=={'DeploymentPreset'}
