import pytest
from maalimbus.team_vision import card_states, participants, team_row,team_header
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


CARD = (190, 248)


def cards(badges):
    """Twelve card boxes in reading order, and a badge caption per badge."""
    boxes = [(355 + 195 * (index % 6), 236 + 296 * (index // 6)) + CARD
             for index in range(12)]
    records = []
    for index, badge in enumerate(badges):
        if badge:
            x, y, w, h = boxes[index]
            records.append(Text(badge, (x + 29, y + 121, 120, 36), 1.0))
    return records, boxes


def test_the_participant_counter_says_when_the_team_is_full():
    # Live proof: build/live-prebattle.png (window-20261007-001439) prints '11/11' at
    # 1920 [1702,754,122,57] score .99 under a bright To Battle!, with eleven badges and
    # a twelfth card slot this encounter does not have.
    size = (1920, 1080)
    full = [Text('11/11', (1702, 754, 122, 57), .99)]
    assert participants(full, size) == (11, 11)
    # An empty page prints 0/12, which is not full.
    assert participants([Text('0/12', (1702, 754, 100, 57), .98)], size) == (0, 12)
    # A counter outside its own corner of the page is not the counter.
    assert participants([Text('11/11', (400, 300, 122, 57), .99)], size) is None
    assert participants([], size) is None


def test_card_states_read_badges_in_reading_order():
    # Live proof: evidence/runtime/window-20261006-030941/frame-0022.json is 12/12 —
    # seven SELECTED then five BACKUP — while window-20261006-030750 is 0/12.
    records, boxes = cards(['SELECTED'] * 7 + ['BACKUP'] * 5)
    assert card_states(records, boxes, (1920, 1080)) == ['selected'] * 7 + ['backup'] * 5
    assert card_states([], boxes, (1920, 1080)) == [None] * 12


def test_card_state_ignores_identity_artwork_that_wears_the_badge_colour():
    # The 0/12 frame has four identities painted in exactly the SELECTED red and one
    # in the BACKUP teal; only the caption may count, never the pixels.
    records, boxes = cards([None] * 12)
    records.append(Text('Kurokumo Clan', (400, 700, 148, 22), .99))
    assert card_states(records, boxes, (1920, 1080)) == [None] * 12


def test_card_state_needs_a_caption_inside_the_card():
    records, boxes = cards([None] * 12)
    # A SELECTED caption from a different card, and one below the badge threshold.
    records.append(Text('SELECTED', (1600, 640, 120, 36), 1.0))
    records.append(Text('BACKUP', (355 + 29, 532 + 121, 104, 41), .42))
    assert card_states(records, boxes, (1920, 1080)) == [None] * 12
    # A missing card box is reported as unknown rather than guessed at.
    assert card_states(records, [None] + boxes[1:], (1920, 1080)) == [None] * 12
