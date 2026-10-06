import pytest
from maalimbus.identity_catalog import (archetypes, by_id, collect_buff_keywords,
                                         keyword_for_buff, merge, with_keyword)


def personality(identity_id=10101, sinner=1, rank=1, skill_id=1010101):
    return {'id': identity_id, 'characterId': sinner, 'rank': rank,
            'hp': {'defaultStat': 72, 'incrementByLevel': 2.48},
            'unitKeywordList': ['FIXER', 'SMALL'], 'associationList': ['SEVEN'],
            'resistInfo': {'atkResistList': [{'type': 'SLASH', 'value': 2},
                                             {'type': 'PENETRATE', 'value': 0.5},
                                             {'type': 'HIT', 'value': 1},
                                             {'type': 'IGNORED', 'value': 9}]},
            'attributeList': [{'skillId': skill_id, 'number': 3}],
            'defenseSkillIDList': [1010104]}


def skill(skill_id=1010101, keyword='Laceration'):
    return {'id': skill_id, 'skillTier': 1, 'skillData': [{'coinList': [
        {'abilityScriptList': [{'scriptName': 'GiveBuffOnSucceedAttack',
                                'buffData': {'buffKeyword': keyword, 'stack': 6}}]}]}]}


def names():
    return {10101: {'name': '李箱', 'title': 'LCB\n罪人'}}


def units():
    return {'FIXER': '收尾人', 'UnitKeyword_FIXER': '收尾人', 'SMALL': '小型', 'SEVEN': '七协会'}


def test_game_buff_keywords_map_to_the_team_vocabulary():
    assert keyword_for_buff('Burst') == 'Rupture'
    assert keyword_for_buff('BurstVulnerable') == 'Rupture'
    assert keyword_for_buff('Laceration') == 'Bleed'
    assert keyword_for_buff('Bleeding') == 'Bleed'
    assert keyword_for_buff('VibrationExplosion') == 'Tremor'
    assert keyword_for_buff('VibrationBleeding') == 'Tremor'
    assert keyword_for_buff('Combustion') == 'Burn'
    assert keyword_for_buff('Breath') == 'Poise'
    assert keyword_for_buff('') is None and keyword_for_buff(None) is None
    assert keyword_for_buff('SomeUnknownKeyword') is None
    assert archetypes(['Burst', 'BurstVulnerable', 'Unknown']) == ['Rupture']


def test_collect_buff_keywords_walks_every_nesting():
    payload = [{'skillData': [{'coinList': [{'abilityScriptList': [
        {'buffData': {'buffKeyword': 'Burst'}}]}, {'x': {'buffKeyword': 'Sinking'}}]}]}]
    assert collect_buff_keywords(payload) == {'Burst', 'Sinking'}
    assert collect_buff_keywords(None) == set()


def test_merge_builds_a_sorted_catalog_from_downloaded_payloads():
    catalog = merge([personality(), personality(10102, 1, 2, 1010102)],
                    [skill(), skill(1010102, 'Burst')], names(), units(),
                    source=['https://example.invalid'], commit={'repo': 'deadbeef'})
    assert catalog['version'] == 1 and catalog['source'] == ['https://example.invalid']
    assert catalog['commit'] == {'repo': 'deadbeef'}
    assert [i['id'] for i in catalog['identities']] == [10101, 10102]
    first = catalog['identities'][0]
    assert first['name'] == '李箱' and first['title'] == 'LCB 罪人'
    assert first['sinner'] == 1 and first['sinner_name'] == 'Yi Sang'
    assert first['keywords'] == ['Bleed'] and first['buff_keywords'] == ['Laceration']
    assert first['unit_keywords'] == ['收尾人', '小型'] and first['association'] == ['七协会']
    assert first['resistances'] == {'SLASH': 2, 'PENETRATE': 0.5, 'HIT': 1}
    assert first['skills'] == [1010101, 1010104]
    assert first['hp_default'] == 72 and first['rank'] == 1
    assert catalog['identities'][1]['keywords'] == ['Rupture']
    assert by_id(catalog)[10102]['id'] == 10102


def test_merge_rejects_malformed_input_and_keeps_unknown_names_empty():
    with pytest.raises(ValueError):
        merge([personality(), personality()], [skill()], names(), units())
    with pytest.raises(ValueError):
        merge([{'id': 'not-an-int'}], [], {}, {})
    catalog = merge([personality(10512, 13)], [], {}, {})
    assert catalog['identities'][0]['name'] == '' and catalog['identities'][0]['keywords'] == []


def test_with_keyword_orders_by_rank_then_hp():
    low = personality(10101, 1, 1, 1010101)
    high = personality(10103, 1, 3, 1010103)
    high['hp'] = {'defaultStat': 90, 'incrementByLevel': 3.0}
    catalog = merge([low, high], [skill(1010101), skill(1010103)], names(), units())
    found = with_keyword(catalog, 1, 'Bleed')
    assert [i['id'] for i in found] == [10103, 10101]
    assert with_keyword(catalog, 1, 'Bleed', owned={10101}) == [catalog['identities'][0]]
    assert with_keyword(catalog, 2, 'Bleed') == []
