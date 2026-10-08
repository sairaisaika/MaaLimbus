import json
from pathlib import Path
import pytest
from maalimbus.global_settings import apply_builds
from maalimbus.policies import Team
from maalimbus.storage import ProfileStore, SINNERS, write_json


def edit(order=SINNERS):
    return dict(edit=True, name='Charge and Tremor', keywords=['Charge', 'Tremor'],
                deployment={str(n): s for n, s in enumerate(order, 1)})


def test_global_edit_preserves_other_metadata_and_rotation_order(tmp_path):
    store = ProfileStore(tmp_path/'user-team-profiles.json')
    original = [Team(5, frozenset({'Burn'})), Team(2, frozenset({'Bleed'}),
                allow=frozenset({'Portable Battery Socket'}), pack_weights=(('ASEA', 20),))]
    store.save(original)
    assert apply_builds(tmp_path, {'2': edit(tuple(reversed(SINNERS)))}) == [2]
    actual = store.load()
    assert actual[0] == original[0] and actual[1].allow == original[1].allow
    assert actual[1].pack_weights == original[1].pack_weights
    assert actual[1].deployment == tuple(reversed(SINNERS))
    assert actual[1].keywords == frozenset({'Charge', 'Tremor'})
    assert apply_builds(tmp_path, {'2': edit(tuple(reversed(SINNERS)))}) == []


def test_saved_default_does_not_replace_or_create_profiles(tmp_path):
    assert apply_builds(tmp_path, {}) == []
    assert not (tmp_path/'user-team-profiles.json').exists()


@pytest.mark.parametrize('fault', ['duplicate', 'missing', 'unknown', 'implicit', 'active'])
def test_invalid_second_edit_never_partially_replaces_first(tmp_path, fault):
    store = ProfileStore(tmp_path/'user-team-profiles.json')
    store.save([Team(1, frozenset({'Bleed'})), Team(2, frozenset({'Burn'}))])
    before = store.path.read_bytes()
    bad = edit()
    if fault == 'duplicate': bad['deployment']['12'] = SINNERS[0]
    if fault == 'missing': del bad['deployment']['12']
    if fault == 'unknown': bad['keywords'] = ['unknown']
    if fault == 'implicit': bad['edit'] = False
    if fault == 'active': write_json(tmp_path/'user-run-ledger.json', {'active': {'team': 2}})
    with pytest.raises(ValueError): apply_builds(tmp_path, {'1': edit(), '2': bad})
    assert store.path.read_bytes() == before


def test_native_global_sections_use_independent_keys_and_start_before_mirror():
    root = Path(__file__).resolve().parents[1]
    pi = json.loads((root/'assets/interface.json').read_text(encoding='utf-8'))
    assert len(pi['setting']) == len(pi['global_option']) == 20
    assert len(set(pi['global_option'])) == 20
    for slot in range(1, 21):
        name = f'global_team_{slot}'
        option = pi['option'][name]
        assert option['default_case'] == 'saved'
        assert 'pipeline_override' not in option['cases'][0]
        assert len(option['cases'][1]['option']) == 14
    task = next(t for t in pi['task'] if t['name'] == 'mirror_loop')
    assert task['entry'] == 'GlobalSettingsApply'
    nodes = json.loads((root/'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf-8'))
    assert nodes['GlobalSettingsApply']['next'] == ['MirrorLoop']
