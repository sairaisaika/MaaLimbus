import pytest
from maalimbus.policies import Team,RunLedger
from maalimbus.storage import ProfileStore,SINNERS


def test_game_team22_burn_tremor_and_boundary40_round_trip(tmp_path):
    teams=(Team(22,frozenset({'Burn','Tremor'}),deployment=SINNERS,auto_team=True),
           Team(40,frozenset({'Burn'})))
    store=ProfileStore(tmp_path/'profiles.json');assert store.save(teams)==teams
    assert RunLedger((22,40)).team_slots==(22,40)


@pytest.mark.parametrize('slot',[0,41,True,'22'])
def test_invalid_slots_do_not_become_game_targets(slot):
    with pytest.raises(ValueError):Team(slot,frozenset())


def test_all_queue_positions_bind_selected_slot_independently():
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    pi=json.loads((root/'assets/interface.json').read_text(encoding='utf-8'))
    for position in range(1,41):
        for case in pi['option'][f'mirror_queue_{position}']['cases']:
            assert case['pipeline_override'][f'MirrorTaskQueue{position}']['attach']['slot']==int(case['name'])
