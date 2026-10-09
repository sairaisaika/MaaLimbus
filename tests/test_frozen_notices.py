import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('frozen_notices',
    Path(__file__).resolve().parents[1]/'tools/frozen_notices.py')
notices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notices)


def fixture(tmp_path, monkeypatch, files=('sample.dist-info/licenses/LICENSE',)):
    monkeypatch.setattr(notices, 'DISTRIBUTIONS', ('sample',))
    source = tmp_path/'source'
    for member in files:
        path = source/member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'original license\r\n')
    python = tmp_path/'python'
    python.mkdir()
    (python/'LICENSE.txt').write_bytes(b'Python license\n')
    dist = SimpleNamespace(version='1.2.3', files=files, locate_file=lambda p: source/p)
    return lambda name: dist, python


def test_exact_notice_bytes_versions_and_provenance(tmp_path, monkeypatch):
    distribution, python = fixture(tmp_path, monkeypatch)
    output = tmp_path/'out'
    proof = notices.collect(output, distribution=distribution, python_root=python)
    assert (output/'sample/licenses/LICENSE').read_bytes()==b'original license\r\n'
    assert proof['components']['sample']['version']=='1.2.3'
    assert not proof['complete_dependency_audit']
    assert not proof['frozen_binary_origin_verified']


@pytest.mark.parametrize('fault', ['missing', 'empty', 'unsafe'])
def test_bad_metadata_fails_before_materializing_notices(tmp_path, monkeypatch, fault):
    members = () if fault=='missing' else ('sample.dist-info/licenses/LICENSE',)
    distribution, python = fixture(tmp_path, monkeypatch, members)
    if fault=='empty':
        (tmp_path/'source'/members[0]).write_bytes(b'')
    if fault=='unsafe':
        distribution=lambda name: SimpleNamespace(version='1',
            files=['sample.dist-info/../LICENSE'], locate_file=lambda p: tmp_path/p)
    output = tmp_path/'out'
    with pytest.raises(ValueError):
        notices.collect(output, distribution=distribution, python_root=python)
    assert not output.exists()
