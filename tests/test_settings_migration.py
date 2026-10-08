import json
from pathlib import Path
from copy import deepcopy
from maalimbus.settings_migration import seed_editors
from maalimbus.policies import Team
from maalimbus.storage import SINNERS


PI=json.loads((Path(__file__).resolve().parents[1]/'assets/interface.json').read_text(encoding='utf-8'))


def test_existing_named_order_system_seed_and_second_import_is_unchanged():
    team=Team(2,frozenset({'Charge','Tremor'}),'My saved team',deployment=tuple(reversed(SINNERS)))
    original={'globalOptionValues':{'unrelated':{'type':'select','caseName':'keep'}}}
    actual,changed=seed_editors(original,PI,[team])
    assert len(changed)==15 and original['globalOptionValues'].keys()=={'unrelated'}
    values=actual['globalOptionValues']
    assert values['global_team_2']['caseName']=='saved'
    assert values['global_team_2_name']['values']['name']==team.name
    assert values['global_team_2_order_1']['caseName']==SINNERS[-1]
    assert values['unrelated']==original['globalOptionValues']['unrelated']
    again,changed=seed_editors(actual,PI,[team])
    assert again==actual and not changed


def test_explicit_edit_or_customized_field_is_never_replaced():
    team=Team(2,frozenset({'Bleed'}),deployment=SINNERS)
    for values in ({'global_team_2':{'type':'select','caseName':'edit'}},
                   {'global_team_2_name':{'type':'input','values':{'name':'User changed name'}}}):
        original={'globalOptionValues':values}
        actual,changed=seed_editors(original,PI,[team])
        assert actual==original and not changed


def test_unsupported_system_or_incomplete_deployment_keeps_editor_untouched():
    for team in (Team(1,frozenset({'Bleed','Charge'}),deployment=SINNERS),
                 Team(1,frozenset({'Bleed'}),deployment=SINNERS[:3])):
        original={'globalOptionValues':{}}
        actual,changed=seed_editors(original,PI,[team])
        assert actual==original and not changed
