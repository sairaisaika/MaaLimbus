import importlib.util
import json
import tomllib
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location('build_package', Path(__file__).resolve().parents[1]/'tools/build_windows_package.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


@pytest.mark.parametrize('names', [['../escape'], ['/absolute'], ['folder\\escape'],
                                  ['C:drive'], ['same', 'SAME'], ['trailing.']])
def test_archive_prevalidation_creates_no_files_for_unsafe_members(tmp_path, names):
    archive = tmp_path/'input.zip'
    with zipfile.ZipFile(archive, 'w') as file:
        file.writestr('first-safe', b'ok')
        for name in names:
            # ZipInfo's Windows constructor normalizes backslashes; preserve the
            # raw hostile member as it would arrive from a foreign archive.
            member = zipfile.ZipInfo()
            member.filename = name
            file.writestr(member, b'bad')
    destination = tmp_path/'stage'
    with pytest.raises(ValueError):
        package.extract_checked(archive, destination)
    assert not destination.exists()


def test_the_five_floor_gap_leaves_the_list_only_with_the_claim():
    unproven = package.pending_items(verified_dungeon_clear=False)
    claimed = package.pending_items(verified_dungeon_clear=True)
    assert 'full five-floor loop' in unproven
    assert 'full five-floor loop' not in claimed
    # Every other gap is a property of the package, not of the live loop.
    assert [p for p in unproven if p != 'full five-floor loop'] == claimed


def test_public_source_archive_excludes_configuration_and_evidence(tmp_path, monkeypatch):
    for name in ('src', 'agent', 'tools', 'tests', 'docs', 'assets', 'THIRD_PARTY_NOTICES'):
        (tmp_path/name).mkdir()
        (tmp_path/name/'public.txt').write_text('public')
    for name in ('README.md','README_en.md','LICENSE','pyproject.toml','PROJECT.md','.gitignore'):
        (tmp_path/name).write_text('public')
    for name in ('build','config','evidence'):
        (tmp_path/name).mkdir()
        (tmp_path/name/'account.txt').write_text('private')
    (tmp_path/'src/__pycache__').mkdir()
    (tmp_path/'src/__pycache__/module.pyc').write_bytes(b'cache')
    monkeypatch.setattr(package, 'ROOT', tmp_path)
    package.copy_public_sources(tmp_path/'source.zip')
    with zipfile.ZipFile(tmp_path/'source.zip') as file:
        assert len(file.namelist()) == 13
        assert all('account' not in p and '__pycache__' not in p for p in file.namelist())


def license_inputs(tmp_path,monkeypatch):
    monkeypatch.setattr(package,'ROOT',tmp_path)
    (tmp_path/'THIRD_PARTY_NOTICES').mkdir()
    inputs={}
    for key,(runtime_member,source_member,notice) in package.SOURCE_LICENSES.items():
        (tmp_path/'THIRD_PARTY_NOTICES'/notice).write_bytes(b'exact license\n')
        for suffix,member in [('',runtime_member),('_source',source_member)]:
            path=tmp_path/(key+suffix+'.zip');inputs[key+suffix]=path
            with zipfile.ZipFile(path,'w') as z:z.writestr(member,b'exact license\n')
    return inputs


def test_runtime_sources_and_notice_are_bound_by_exact_bytes(tmp_path,monkeypatch):
    inputs=license_inputs(tmp_path,monkeypatch)
    result=package.verify_corresponding_licenses(inputs)
    assert set(result)=={'mxu','maa'}
    assert all(p['exact_bytes_match'] for p in result.values())


@pytest.mark.parametrize('fault',['different','missing','duplicate'])
def test_unbound_corresponding_source_is_rejected(tmp_path,monkeypatch,fault):
    inputs=license_inputs(tmp_path,monkeypatch)
    member=package.SOURCE_LICENSES['maa'][1]
    with zipfile.ZipFile(inputs['maa_source'],'w') as z:
        z.writestr('wrong' if fault=='missing' else member,b'changed' if fault=='different' else b'exact license\n')
        if fault=='duplicate':
            with pytest.warns(UserWarning):z.writestr(member,b'exact license\n')
    with pytest.raises(ValueError):package.verify_corresponding_licenses(inputs)


def test_project_and_native_interface_version_agree():
    root=Path(__file__).resolve().parents[1]
    version=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
    assert json.loads((root/'assets/interface.json').read_text())['version']=='v'+version
