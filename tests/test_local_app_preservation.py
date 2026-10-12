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


def helpers_at(root):
    leaf=root/'maatouch'/'universal';leaf.mkdir(parents=True)
    (leaf/'maatouch').write_bytes(b'#!')
    return root


def test_the_packaging_step_ships_the_input_helpers():
    # Live 2026-10-12: the assembled app shipped the MaaFramework DLLs but no
    # MaaAgentBinary, so MXU's agent_path named a missing directory, Maatouch failed
    # to initialize and every click fell back to `adb shell input tap`, which the game
    # ignores. The staging step must copy the helpers next to MaaFramework.dll.
    source=Path(module.__file__).read_text(encoding='utf-8')
    assert "staged/'maafw'/'MaaAgentBinary'" in source
    assert "raise ValueError(" in source and 'MaaAgentBinary' in source


def test_agent_binaries_prefers_the_explicit_path(tmp_path):
    explicit=helpers_at(tmp_path/'wheel'/'MaaAgentBinary')
    assert module.agent_binaries(explicit)==explicit


def test_agent_binaries_rejects_a_directory_without_the_helper(tmp_path):
    empty=tmp_path/'empty';empty.mkdir()
    assert module.agent_binaries(empty,prepared=tmp_path/'prepared') is None


def test_agent_binaries_falls_back_to_the_prepared_release(tmp_path,monkeypatch):
    share=helpers_at(tmp_path/'maa'/'share'/'MaaAgentBinary')
    monkeypatch.setattr(module.importlib.util,'find_spec',lambda name:None)
    assert module.agent_binaries(None,prepared=tmp_path/'MaaLimbus-win-x64')==share


def test_agent_binaries_prefers_the_wheel_over_the_prepared_release(tmp_path):
    wheel=module.agent_binaries(None,prepared=Path('no-such-prepared-release'))
    if wheel is None:
        pytest.skip('this environment has no MaaFw wheel shipping MaaAgentBinary')
    prepared=helpers_at(tmp_path/'maa'/'share'/'MaaAgentBinary')
    assert module.agent_binaries(None,prepared=tmp_path/'MaaLimbus-win-x64')==wheel
    assert prepared!=wheel


def test_the_installed_wheel_can_supply_the_helpers():
    located=module.agent_binaries(None,prepared=Path('no-such-prepared-release'))
    if located is None:
        pytest.skip('this environment has no MaaFw wheel shipping MaaAgentBinary')
    assert (located/'maatouch/universal/maatouch').is_file()
