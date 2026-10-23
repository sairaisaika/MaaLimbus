import json
from maalimbus import gui_preferences


def _config(team='2', systems='Charge+Tremor', keyword='saved', search='saved'):
    return {'instances': [{'tasks': [{'optionValues': {
        'mirror_team_mode': {'caseName': 'single'},
        'mirror_single_team': {'caseName': team},
        'mirror_initial_keyword': {'caseName': keyword},
        'mirror_gift_search': {'caseName': search},
        'mirror_run_count': {'caseName': '3'},
    }}]}],
        'globalOptionValues': {f'global_team_{team}_systems': {'caseName': systems},
                               f'global_team_{team}_name': {'name': 'Team 2'}}}


def _write(tmp_path, data):
    path = tmp_path / 'mxu.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def test_the_players_team_and_systems_are_read(tmp_path):
    prefs = gui_preferences.read(_write(tmp_path, _config()))
    assert prefs['mirror_single_team'] == 2
    assert prefs['team_systems'] == 'Charge+Tremor'
    assert prefs['mirror_initial_keyword'] == 'saved'
    assert prefs['mirror_run_count'] == '3'


def test_a_missing_field_is_not_invented(tmp_path):
    data = _config()
    del data['instances'][0]['tasks'][0]['optionValues']['mirror_single_team']
    prefs = gui_preferences.read(_write(tmp_path, data))
    assert prefs['mirror_single_team'] is None
    assert prefs['team_systems'] is None


def test_an_unreadable_file_is_empty_not_a_guess(tmp_path):
    assert gui_preferences.read(tmp_path / 'absent.json') == {}
    broken = tmp_path / 'broken.json'
    broken.write_text('{not json', encoding='utf-8')
    assert gui_preferences.read(broken) == {}


def test_the_evidence_line_names_the_team(tmp_path):
    prefs = gui_preferences.read(_write(tmp_path, _config()))
    assert 'team 2' in gui_preferences.describe(prefs)
    assert 'Charge+Tremor' in gui_preferences.describe(prefs)
    assert gui_preferences.describe({}) == 'no_gui_preferences'
