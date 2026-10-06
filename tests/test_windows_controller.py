import json
from pathlib import Path

import pytest

from maalimbus.windows_controller import controller_profile, native_methods, DEFAULT_CONTROLLER

ROOT = Path(__file__).resolve().parents[1]
INTERFACE = ROOT / 'assets/interface.json'


def test_reference_profiles_resolve_to_native_methods_and_keep_existing_name():
    all_profiles = json.loads(INTERFACE.read_text(encoding='utf-8'))['controller']
    profiles = [p for p in all_profiles if p['type']=='Win32']
    android=[p for p in all_profiles if p['type']=='Adb']
    assert len(android)==1 and android[0]['name']=='mumu-adb'
    assert android[0]['display_long_side']==1920
    assert profiles[0]['name'] == DEFAULT_CONTROLLER
    assert {p['name'] for p in profiles} == {'windows-window', 'windows-background', 'windows'}
    for profile in profiles:
        assert profile['permission_required']
        assert all(int(method) != 0 for method in native_methods(profile))
    window = controller_profile(INTERFACE, DEFAULT_CONTROLLER)
    assert [int(x) for x in native_methods(window)] == [18, 32, 4]
    assert [int(x) for x in native_methods(controller_profile(INTERFACE, 'windows-background'))] == [18, 128, 4]
    assert [int(x) for x in native_methods(controller_profile(INTERFACE, 'windows'))] == [32, 1, 1]
    with pytest.raises(ValueError):
        controller_profile(INTERFACE, 'missing')


def test_all_native_ui_languages_resolve_labels_and_icon_exists():
    interface = json.loads(INTERFACE.read_text(encoding='utf-8'))
    def strings(value):
        if isinstance(value, dict):
            for v in value.values():
                yield from strings(v)
        elif isinstance(value, list):
            for v in value:
                yield from strings(v)
        elif isinstance(value, str) and value.startswith('$'):
            yield value[1:]
    for language in interface['languages'].values():
        catalog = json.loads((ROOT/'assets'/language).read_text(encoding='utf-8'))
        assert set(strings(interface)).issubset(catalog)
    assert (ROOT/'assets'/interface['icon']).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
