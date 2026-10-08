import importlib.util
from pathlib import Path
import pytest
from maalimbus.storage import write_json

spec=importlib.util.spec_from_file_location('local_app',Path(__file__).resolve().parents[1]/'tools/make_local_app.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Lease:
    def __init__(self,path):pass
    def close(self):pass


def setup(tmp_path):
    old=tmp_path/'app';old.mkdir()
    (old/'MaaLimbus.exe').write_bytes(b'old')
    write_json(old/'interface.json',dict(name='MaaLimbus',interface_version=2,version='v0.1.0',
                                       github='https://github.com/sairaisaika/MaaLimbus'))
    (old/'config').mkdir();(old/'config/mxu-MaaLimbus.json').write_bytes(b'user queue and UI settings')
    staged=tmp_path/'staged';staged.mkdir();(staged/'MaaLimbus.exe').write_bytes(b'new')
    return staged,old


def test_desktop_rebuild_preserves_actual_config_and_retains_backup(tmp_path):
    staged,old=setup(tmp_path)
    result=module.replace_local_app(staged,old,process_check=lambda app:None,
        validator=lambda app:{'agent_self_test':True},lease_factory=Lease)
    assert (old/'config/mxu-MaaLimbus.json').read_bytes()==b'user queue and UI settings'
    assert (old/'MaaLimbus.exe').read_bytes()==b'new'
    assert (Path(result['backup'])/'MaaLimbus.exe').read_bytes()==b'old'


def test_failed_desktop_rebuild_restores_old_config_and_executable(tmp_path):
    staged,old=setup(tmp_path)
    with pytest.raises(ValueError):
        module.replace_local_app(staged,old,process_check=lambda app:None,
            validator=lambda app:{'agent_self_test':False},lease_factory=Lease)
    assert (old/'MaaLimbus.exe').read_bytes()==b'old'
    assert (old/'config/mxu-MaaLimbus.json').read_bytes()==b'user queue and UI settings'


def test_running_desktop_is_not_replaced(tmp_path):
    staged,old=setup(tmp_path)
    def busy(app):raise ValueError('Still running')
    with pytest.raises(ValueError):
        module.replace_local_app(staged,old,process_check=busy,lease_factory=Lease)
    assert (old/'MaaLimbus.exe').read_bytes()==b'old'
    assert staged.is_dir()
