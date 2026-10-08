"""The assets must follow the MaaFramework protocols they name.

`tools/verify_pipeline_spec.py` carries the reading of the manual (ProjectInterface V2
for `assets/interface.json`, the task-pipeline protocol for the nodes, the custom
action/recognition registration rule for this agent). These tests keep the repository
on the right side of it, so a node that names an action the agent never registered
fails here instead of at run time on a device.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('verify_pipeline_spec', ROOT / 'tools/verify_pipeline_spec.py')
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)


def pipeline():
    path = ROOT / 'assets/resource/base/pipeline/mirror.json'
    return json.loads(path.read_text(encoding='utf-8'))


def interface():
    return json.loads((ROOT / 'assets/interface.json').read_text(encoding='utf-8'))


def test_every_custom_name_the_pipeline_uses_is_registered():
    registered = verify.registered_names(ROOT / 'agent/main.py')
    problems: list = []
    verify.check_pipeline(pipeline(), registered=registered, entries=[], problems=problems)
    assert [p for p in problems if 'is not registered' in p] == []


def test_the_map_and_battle_observers_are_registered_by_name():
    # `MapObserve` and `BattleObserve` are read-only recorders the pipeline and the
    # toolkit drive; the protocol refuses a node whose action was never registered.
    registered = verify.registered_names(ROOT / 'agent/main.py')
    assert {'limbus_map_observe', 'limbus_battle_observe'} <= registered


def test_a_node_naming_an_unregistered_action_is_reported():
    registered = verify.registered_names(ROOT / 'agent/main.py')
    body = dict(pipeline())
    body['MapObserve'] = dict(body['MapObserve'], custom_action='limbus_nonexistent')
    problems: list = []
    verify.check_pipeline(body, registered=registered, entries=[], problems=problems)
    assert any("limbus_nonexistent" in p and 'is not registered' in p for p in problems)


def test_every_pipeline_target_exists():
    problems: list = []
    verify.check_pipeline(pipeline(), registered=verify.registered_names(ROOT / 'agent/main.py'),
                          entries=[], problems=problems)
    assert [p for p in problems if 'is not a node' in p] == []


def test_interface_json_is_protocol_two_and_names_real_nodes():
    problems: list = []
    verify.check_interface(interface(), set(pipeline()), root=ROOT, problems=problems)
    assert problems == []


def test_the_adb_controller_leaves_screencap_and_input_to_the_framework():
    # docs/zh_cn/3.3-ProjectInterfaceV2协议.md:191 — an Adb controller's input and
    # screencap are auto-detected; a manual choice here would be our invention.
    for controller in interface()['controller']:
        if controller.get('type') == 'Adb':
            assert 'screencap' not in controller.get('adb', {})
            assert 'input' not in controller.get('adb', {})


def test_a_controller_type_outside_the_protocol_is_reported():
    body = json.loads(json.dumps(interface()))
    body['controller'][0]['type'] = 'AdbPlus'
    problems: list = []
    verify.check_interface(body, set(pipeline()), root=ROOT, problems=problems)
    assert any('AdbPlus' in p for p in problems)


def test_two_scaling_modes_on_one_controller_are_reported():
    body = json.loads(json.dumps(interface()))
    body['controller'][0]['display_short_side'] = 720
    problems: list = []
    verify.check_interface(body, set(pipeline()), root=ROOT, problems=problems)
    assert any('mutually exclusive' in p for p in problems)


def test_an_override_that_names_no_node_is_reported():
    body = json.loads(json.dumps(interface()))
    option = body['option']['team_slot']
    option['cases'][0].setdefault('pipeline_override', {})['NoSuchNode'] = {'enabled': True}
    problems: list = []
    verify.check_interface(body, set(pipeline()), root=ROOT, problems=problems)
    assert any('NoSuchNode' in p for p in problems)
