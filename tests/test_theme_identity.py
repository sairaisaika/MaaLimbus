"""One pack, one identity: a header the page truncated and a name OCR misspelled (D124).

Live `packaged-mirror-20261024-132342` selected `Vield My Flesh to Claim Their Bones BokGak`
(what the selection page read) and met a map header reading `Yield My Flesh to Claim Their`;
the transaction called that a mismatch and ended a run at 292 s of a 420 s budget.
"""
import json
import pathlib

import pytest

from maalimbus.theme_transaction import ThemeTransaction
from maalimbus.theme_vision import ThemeCatalog

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'assets/resource/base'


def _catalog():
    return ThemeCatalog(CATALOG)


def test_the_two_live_spellings_are_one_pack():
    catalog = _catalog()
    selected = catalog.identity('Vield My Flesh to Claim Their Bones BokGak')
    header = catalog.identity('Yield My Flesh to Claim Their')
    assert selected == header == 'Yield My Flesh to Claim Their Bones'


def test_a_truncated_header_still_names_its_pack():
    catalog = _catalog()
    assert catalog.identity('Crushing External Force') == 'Crushing External Force'
    assert catalog.identity('Emotional Judgment') == 'Emotional Judgment'


def test_a_name_the_catalog_does_not_hold_is_not_an_identity():
    assert _catalog().identity('Zzz nothing like a theme') is None
    assert _catalog().identity('') is None


def test_the_declared_alias_is_recorded_with_its_evidence():
    catalog = _catalog()
    assert catalog.merged and all(row.get('declared') for row in catalog.merged)
    assert {row['name'] for row in catalog.merged} == set(catalog.aliases)


def test_an_alias_that_names_nothing_is_refused(tmp_path):
    data = json.loads((CATALOG / 'theme-catalog.json').read_text(encoding='utf-8'))
    data['aliases'] = {'Not A Theme': data['names'][0]['name']}
    bad = tmp_path / 'catalog'
    bad.mkdir()
    (bad / 'theme-catalog.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    for entry in data['glyphs'].values():
        target = bad / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((CATALOG / entry['path']).read_bytes())
    with pytest.raises(ValueError, match='does not list'):
        ThemeCatalog(bad)


def test_the_transaction_now_proves_the_successor_it_used_to_refuse(tmp_path):
    catalog = _catalog()
    ledger = tmp_path / 'user-theme-transaction.json'
    transaction = ThemeTransaction(ledger)
    transaction.intent('run-1', 4, 'Vield My Flesh to Claim Their Bones BokGak',
                       tmp_path / 'selection.json')


    class Header:
        floor = 4
        pack = 'Yield My Flesh to Claim Their'

    assert transaction.observe('run-1', Header(), catalog, tmp_path / 'map.json') is True
    data = json.loads(ledger.read_text(encoding='utf-8'))
    assert data['pending'] is None
    assert data['selected'][0]['name'] == 'Vield My Flesh to Claim Their Bones BokGak'


def test_a_different_floor_is_still_a_mismatch(tmp_path):
    catalog = _catalog()
    transaction = ThemeTransaction(tmp_path / 'ledger.json')
    transaction.intent('run-1', 4, 'Crushing External Force', tmp_path / 'selection.json')

    class Header:
        floor = 3
        pack = 'Crushing External Force'

    with pytest.raises(ValueError, match='not proven'):
        transaction.observe('run-1', Header(), catalog, tmp_path / 'map.json')
