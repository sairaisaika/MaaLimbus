import json
import os
from types import SimpleNamespace
import pytest
from maalimbus.startup_update import startup_update, update_enabled
from maalimbus.storage import write_json
from maalimbus.update_stage import StageError
from maalimbus.controller_lease import lease_path
from maalimbus.update_install import closed_app


def app_fixture(tmp_path):
    app = tmp_path/'app'
    write_json(app/'interface.json', dict(name='MaaLimbus', interface_version=2,
        github='https://github.com/sairaisaika/MaaLimbus', version='v0.1.0'))
    return app


def client(status='available', tag='v0.2.0'):
    class Client:
        def __init__(self, path): pass
        def check(self):
            return dict(status=status, requested=True, retry_at=42,
                        release={'tag_name':tag,'assets':[]})
    return Client


@pytest.mark.parametrize('status', ['network_error','rate_limited','no_release'])
def test_offline_launch_uses_local_app_without_staging(tmp_path, status):
    app = app_fixture(tmp_path)
    def forbidden(*a, **kw): raise AssertionError('Unexpected install/download')
    result = startup_update(app, tmp_path/'work', client_factory=client(status),
                            stage=forbidden, install=forbidden)
    assert result['status'] == status and not result['installed']
    assert result['version_after'] == 'v0.1.0' and result['game_input_sent'] is False


def test_native_disabled_preference_makes_no_network_request(tmp_path):
    app = app_fixture(tmp_path)
    write_json(app/'config/mxu-MaaLimbus.json', {'globalOptionValues':{
        'software_auto_update': {'type':'select','caseName':'disabled'}}})
    def forbidden(*a, **kw): raise AssertionError('Unexpected network request')
    assert startup_update(app,tmp_path/'work',client_factory=forbidden,install=forbidden)['status']=='disabled'


def test_newer_release_installs_before_open_and_records_actual_metadata(tmp_path):
    app=app_fixture(tmp_path); calls=[]
    def stage(release,root,**kw):
        calls.append('stage');return {'status':'staged','stage':str(root/'x')}
    def install(path,target):
        calls.append('install');info=json.loads((target/'interface.json').read_text())
        info['version']='v0.2.0';write_json(target/'interface.json',info)
        return {'status':'installed','installed':True}
    result=startup_update(app,tmp_path/'work',client_factory=client(),stage=stage,install=install)
    assert calls==['stage','install'] and result['version_after']=='v0.2.0'


@pytest.mark.parametrize('status', ['rolled_back','rollback_failed'])
def test_rollback_can_launch_only_when_old_app_is_restored(tmp_path,status):
    app=app_fixture(tmp_path)
    kwargs=dict(client_factory=client(), stage=lambda *a,**kw:{'status':'staged','stage':str(tmp_path/'stage')},
                install=lambda *a:{'status':status,'installed':False})
    if status=='rolled_back':
        assert startup_update(app,tmp_path/'work',**kwargs)['version_after']=='v0.1.0'
    else:
        with pytest.raises(StageError):startup_update(app,tmp_path/'work',**kwargs)


@pytest.mark.parametrize('tag',['v0.1.0','v0.0.9','invalid'])
def test_same_older_or_invalid_version_never_installs(tmp_path,tag):
    app=app_fixture(tmp_path)
    def forbidden(*a,**kw):raise AssertionError('Unexpected install')
    result=startup_update(app,tmp_path/'work',client_factory=client(tag=tag),stage=forbidden,install=forbidden)
    assert result['status']==('unsupported_release_tag' if tag=='invalid' else 'current')


def test_source_and_installed_controller_locks_are_the_same(tmp_path):
    assert lease_path(tmp_path/'source/build/controller.lock') == lease_path(tmp_path/'installed/build/controller.lock')
    assert lease_path(tmp_path/'launcher.lock') != lease_path(tmp_path/'controller.lock')


@pytest.mark.skipif(os.name!='nt',reason='Windows CIM process identity')
def test_external_launcher_ignores_only_its_own_outside_process(tmp_path,monkeypatch):
    app=app_fixture(tmp_path)
    own={'ProcessId':os.getpid(),'Name':'MaaLimbusLauncher.exe',
         'ExecutablePath':str(tmp_path/'helper/MaaLimbusLauncher.exe'),
         'CommandLine':'helper --app '+str(app/'MaaLimbus.exe')}
    def records(items):
        monkeypatch.setattr('maalimbus.update_install.subprocess.run',
            lambda *a,**kw:SimpleNamespace(returncode=0,stdout=json.dumps(items)))
    records([own])
    closed_app(app,external_launcher_pid=os.getpid())
    records([own,{'ProcessId':99999,'Name':'MaaLimbus.exe',
                  'ExecutablePath':str(app/'MaaLimbus.exe'),'CommandLine':''}])
    with pytest.raises(StageError):closed_app(app,external_launcher_pid=os.getpid())
    own['ExecutablePath']=str(app/'launcher/MaaLimbusLauncher.exe')
    records([own])
    with pytest.raises(StageError):closed_app(app,external_launcher_pid=os.getpid())
