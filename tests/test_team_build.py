"""The team-build entry writes keywords into a saved team and files it.

The nodes are driven from ProjectInterface: `TeamKeywordSet` replaces the build,
`TeamKeywordExtra` unions free-text names onto it, and `TeamBuildSave` files the
name. Everything lands in the same profile file the rest of the agent uses, so a
second saved team must never move.
"""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'agent'))
from recognition import TeamAction, Journal
from maalimbus.policies import Team
from maalimbus.storage import KEYWORDS, ProfileStore


def harness(tmp_path, teams):
    store = ProfileStore(tmp_path/'user-team-profiles.json')
    store.save(list(teams))
    rec = SimpleNamespace(team=None, journal=Journal(tmp_path/'journal'))
    action = TeamAction(rec)
    def run(params): return action.run(None, SimpleNamespace(custom_action_param=json.dumps(params)))
    return store, rec, run


def events(tmp_path):
    return [json.loads(line) for line in (tmp_path/'journal/events.jsonl').read_text().splitlines()]


def test_the_build_replaces_the_keywords_and_leaves_the_other_team_alone(tmp_path, monkeypatch):
    monkeypatch.setenv('MAALIMBUS_DATA_PATH', str(tmp_path))
    other = Team(7, frozenset({'Bleed'}), name='Untouched')
    store, rec, run = harness(tmp_path, [Team(2, frozenset({'Burn'}), name='Charge'), other])
    assert run({'mode':'keywords','slot':2,'keywords':['Charge','Tremor']})
    saved = ProfileStore(store.path).load()
    assert saved[0].keywords == frozenset({'Charge','Tremor'})
    assert saved[0].name == 'Charge' and saved[1] == other
    assert rec.team == saved[0]
    assert events(tmp_path)[-1]['event'] == 'team_preferences_saved'
    assert events(tmp_path)[-1]['keywords'] == ['Charge','Tremor']


def test_the_extra_keywords_are_added_to_what_the_team_already_carries(tmp_path, monkeypatch):
    monkeypatch.setenv('MAALIMBUS_DATA_PATH', str(tmp_path))
    store, rec, run = harness(tmp_path, [Team(2, frozenset({'Charge'}))])
    # `TeamKeywordSet` runs first and points the action at the saved team; the
    # extra node carries no slot of its own.
    rec.team = ProfileStore(store.path).load()[0]
    assert run({'mode':'keywords_add','keywords':['Tremor']})
    assert ProfileStore(store.path).load()[0].keywords == frozenset({'Charge','Tremor'})


def test_an_unknown_keyword_is_journalled_and_skipped_not_raised(tmp_path, monkeypatch):
    """A typo in the GUI's free-text box must not latch the callback closed."""
    monkeypatch.setenv('MAALIMBUS_DATA_PATH', str(tmp_path))
    store, rec, run = harness(tmp_path, [Team(2, frozenset({'Charge'}))])
    rec.team = ProfileStore(store.path).load()[0]
    assert run({'mode':'keywords','keywords':['Tremor','Tremour']})
    assert ProfileStore(store.path).load()[0].keywords == frozenset({'Tremor'})
    recorded = events(tmp_path)
    assert recorded[-2]['event'] == 'team_keywords_rejected'
    assert recorded[-2]['rejected'] == ['Tremour']
    assert recorded[-1]['event'] == 'team_preferences_saved'
    assert 'callback_failure' not in rec.__dict__


def test_saving_files_the_name_without_touching_the_build(tmp_path, monkeypatch):
    monkeypatch.setenv('MAALIMBUS_DATA_PATH', str(tmp_path))
    store, rec, run = harness(tmp_path, [Team(2, frozenset({'Charge','Tremor'}), name='old')])
    rec.team = ProfileStore(store.path).load()[0]
    assert run({'mode':'save','name':'Charge + Tremor'})
    saved = ProfileStore(store.path).load()[0]
    assert saved.name == 'Charge + Tremor' and saved.keywords == frozenset({'Charge','Tremor'})
    assert events(tmp_path)[-1]['event'] == 'team_build_saved'
    assert run({'mode':'save','name':''}) and ProfileStore(store.path).load()[0].name == 'Charge + Tremor'


def test_the_entry_creates_the_slot_it_was_asked_for_when_nothing_is_selected(tmp_path, monkeypatch):
    monkeypatch.setenv('MAALIMBUS_DATA_PATH', str(tmp_path))
    store, rec, run = harness(tmp_path, [Team(7, frozenset({'Bleed'}))])
    assert run({'mode':'keywords','slot':2,'keywords':['Charge']})
    saved = ProfileStore(store.path).load()
    assert [t.slot for t in saved] == [7, 2] and saved[1].keywords == frozenset({'Charge'})


def test_the_pipeline_chain_and_the_interface_agree_on_the_same_nodes():
    nodes = json.loads((ROOT/'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf-8'))
    pi = json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    assert nodes['TeamKeywordSet']['next'] == ['TeamKeywordExtra']
    assert nodes['TeamKeywordExtra']['next'] == ['TeamBuildSave']
    assert nodes['TeamBuildSave']['next'] == ['MirrorLoop']
    assert nodes['TeamBuildDone']['action'] == 'DoNothing'
    assert nodes['TeamKeywordSet']['custom_action_param']['mode'] == 'keywords'
    assert nodes['TeamKeywordExtra']['custom_action_param']['mode'] == 'keywords_add'
    assert nodes['TeamBuildSave']['custom_action_param']['mode'] == 'save'
    for name in ('TeamKeywordSet','TeamKeywordExtra','TeamBuildSave'):
        assert nodes[name]['custom_action'] == 'limbus_team'
    cases = pi['option']['team_build_slot']['cases']
    assert [c['name'] for c in cases] == [str(i) for i in range(1,21)]
    for case in cases:
        slot = int(case['name'])
        assert case['pipeline_override']['TeamKeywordSet']['custom_action_param']['slot'] == slot
    tasks = {t['name']: t for t in pi['task']}
    assert tasks['team_build']['entry'] == 'TeamKeywordSet'
    # Global settings apply only explicit edits; the legacy build replace chain
    # is not run as part of the Mirror task.
    assert tasks['mirror_loop']['entry'] == 'GlobalSettingsApply'
    assert nodes['GlobalSettingsApply']['next'] == ['MirrorLoop']
    assert all(nodes[f'Global_global_team_{i}']['attach']['global_build']['edit'] is False
               for i in range(1,21))
    assert 'team_keywords' not in tasks['mirror_loop']['option']
    assert 'team_build_slot' in tasks['team_build']['option']
    assert 'team_keywords' in tasks['team_build']['option']
    assert tasks['mirror_loop']['option']==['run_team']
    only_save = tasks['team_build']['pipeline_override']['TeamBuildSave']
    assert only_save['next'] == ['TeamBuildDone']
    assert 'TeamBuildSave' not in tasks['mirror_loop'].get('pipeline_override', {})


def test_every_keyword_a_build_can_name_is_one_the_engine_knows():
    """The GUI offers the same list the profile rejects unknown names against."""
    pi = json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    offered = set(pi['option']['team_keywords']['cases'][0]['pipeline_override']
                    ['TeamKeywordSet']['custom_action_param']['keywords'])
    assert offered and offered <= set(KEYWORDS)
