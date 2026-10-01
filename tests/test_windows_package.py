import importlib.util
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
