import importlib.util
import io
from pathlib import Path
import tarfile

import pytest

spec=importlib.util.spec_from_file_location('native_notices',
    Path(__file__).resolve().parents[1]/'tools/native_dependency_notices.py')
notices=importlib.util.module_from_spec(spec)
spec.loader.exec_module(notices)


def inputs(tmp_path, monkeypatch, *, fault=None):
    runtime, devel, binaries = tmp_path/'runtime.tar', tmp_path/'devel.tar', tmp_path/'bin'
    binaries.mkdir()
    monkeypatch.setattr(notices, 'COMPONENTS', {'example.dll':'example'})
    def write(archive, name, data):
        member=tarfile.TarInfo(name);member.size=len(data)
        archive.addfile(member,io.BytesIO(data))
    (binaries/'example.dll').write_bytes(b'changed' if fault=='binary' else b'runtime')
    with tarfile.open(runtime,'w') as archive:
        write(archive,'runtime/maa-x64-windows/example.dll',b'runtime')
        if fault=='duplicate_binary':write(archive,'runtime/maa-x64-windows/example.dll',b'runtime')
    with tarfile.open(devel,'w') as archive:
        if fault!='missing':
            name='vcpkg/installed/maa-x64-windows/share/example/copyright'
            write(archive,name,b'' if fault=='empty' else b'original notice\r\n')
            if fault=='duplicate_notice':write(archive,name,b'original notice\r\n')
    monkeypatch.setattr(notices,'RUNTIME_SHA',notices.digest(runtime))
    monkeypatch.setattr(notices,'DEVEL_SHA','wrong' if fault=='archive' else notices.digest(devel))
    return runtime,devel,binaries


def test_original_notice_and_binary_bound_before_output(tmp_path,monkeypatch):
    args=inputs(tmp_path,monkeypatch);out=tmp_path/'out'
    proof=notices.collect(*args,out)
    assert (out/'example/copyright').read_bytes()==b'original notice\r\n'
    assert proof['binaries']['example.dll']['component']=='example'
    assert not proof['complete_distribution_audit']


@pytest.mark.parametrize('fault',['archive','binary','missing','empty','duplicate_binary','duplicate_notice'])
def test_invalid_dependency_evidence_creates_no_notices(tmp_path,monkeypatch,fault):
    args=inputs(tmp_path,monkeypatch,fault=fault);out=tmp_path/'out'
    with pytest.raises(ValueError):notices.collect(*args,out)
    assert not out.exists()
