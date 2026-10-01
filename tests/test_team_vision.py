import pytest
from maalimbus.team_vision import team_row,team_header
from maalimbus.policies import Team
from maalimbus.vision import Text,classify
from test_vision import LOCALES
import json


@pytest.mark.parametrize('locale,name',[('en','TEAMS #2'),('jp','チーム #2')])
def test_team_row_is_separate_from_header_and_preset(locale,name):
    team=Team(2,frozenset())
    row=Text(name,(80,390,100,20),.99)
    header=Text(name,(200,110,150,30),.99)
    records=[Text('Preset #2',(90,100,90,20),.99),row,header]
    assert team_row(records,team,locale,(1000,1000))==row
    assert team_header(records,team,locale,(1000,1000))==header
    assert team_row(records+[row],team,locale,(1000,1000)) is None


def test_renamed_team_uses_literal_label_and_no_assumed_ordinal():
    team=Team(8,frozenset(),name='BURN-TREMOR')
    named=Text('BURN-TREMOR',(70,690,100,20),.99)
    assert team_row([named],team,'en',(1000,1000))==named
    assert team_row([named],Team(8,frozenset()),'en',(1000,1000)) is None
    assert team_row([Text('wrong label',(70,690,100,20),.99)],team,'en',(1000,1000)) is None


def test_library_never_claimed_as_dungeon_deployment():
    words=json.loads((LOCALES/'en/locale.json').read_text())
    records=[Text('Details',(710,100,100,30),.99),Text('TEAMS',(80,200,90,30),.99),
             Text('SIN | COST',(800,100,100,30),.99)]
    assert classify(records,words,(1000,1000))=='TEAM_LIBRARY'
    assert classify(records[:2],words,(1000,1000))=='UNKNOWN'
