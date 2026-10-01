import hashlib
import io
import json
from pathlib import Path
import time
import urllib.error
import zipfile

import pytest

from maalimbus.archives import extract_checked
from maalimbus.github_cache import GitHubState
from maalimbus.update_stage import select_assets, stage_release, StageError, HTTPSRedirect


def fixture(extra=None):
    files={name:b'public fixture' for name in ('MaaLimbus.exe','interface.json','LICENSE',
        'build-info.json','agent/MaaLimbusAgent.exe','runner/MaaLimbusRunner.exe')}
    if extra:files.update(extra)
    files['package-manifest.json']=json.dumps({name:hashlib.sha256(data).hexdigest()
        for name,data in files.items()}).encode()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:
        for name,data in files.items():z.writestr(name,data)
    package=buffer.getvalue();name='MaaLimbus-win-x64.zip'
    sums=(hashlib.sha256(package).hexdigest()+'  '+name+'\n').encode()
    payloads={name:package,'SHA256SUMS':sums}
    release={'tag_name':'v0.1.0','assets':[
        {'name':n,'size':len(data),'digest':'sha256:'+hashlib.sha256(data).hexdigest(),
         'browser_download_url':'https://github.com/sairaisaika/MaaLimbus/releases/download/v0.1.0/'+n}
        for n,data in payloads.items()]}
    return release,payloads


def offline(payloads):
    def transport(url,path,size,deadline,proxy):Path(path).write_bytes(payloads[url.rsplit('/',1)[1]])
    return transport


def test_valid_staging_preserves_existing_install_and_does_not_execute(tmp_path):
    install=tmp_path/'install';install.mkdir();(install/'config.json').write_text('keep')
    release,payloads=fixture()
    result=stage_release(release,tmp_path/'updates',transport=offline(payloads))
    assert result['status']=='staged' and result['files']==6
    assert result['installed'] is False and result['executed'] is False
    assert (install/'config.json').read_text()=='keep'
    assert not list(Path(result['stage']).glob('*.part'))
    assert json.loads((Path(result['stage'])/'stage-result.json').read_text())==result
    second=stage_release(release,tmp_path/'updates',transport=offline(payloads))
    assert second['stage']!=result['stage']


@pytest.mark.parametrize('change', ['ambiguous','no_checksum','foreign_url','oversize','draft','development'])
def test_invalid_assets_create_no_stage(tmp_path,change):
    release,payloads=fixture()
    if change=='ambiguous':release['assets'].append(dict(release['assets'][0]))
    if change=='no_checksum':release['assets'].pop()
    if change=='foreign_url':release['assets'][0]['browser_download_url']='https://evil.example/package.zip'
    if change=='oversize':release['assets'][0]['size']=700_000_001
    if change=='draft':release['draft']=True
    if change=='development':release['assets'][0]['name']='MaaLimbus-win-x64-development.zip'
    with pytest.raises(StageError):stage_release(release,tmp_path/'updates',transport=offline(payloads))
    assert not (tmp_path/'updates').exists()


@pytest.mark.parametrize('bad', ['hash','short','private','unlisted'])
def test_bad_package_never_accepted(tmp_path,bad):
    release,payloads=fixture({'config/user.json':b'private'} if bad=='private' else None)
    if bad=='hash':payloads['MaaLimbus-win-x64.zip']=b'X'*len(payloads['MaaLimbus-win-x64.zip'])
    if bad=='short':payloads['MaaLimbus-win-x64.zip']=b'x'
    if bad=='unlisted':
        buffer=io.BytesIO(payloads['MaaLimbus-win-x64.zip'])
        with zipfile.ZipFile(buffer,'a') as z:z.writestr('unexpected.exe',b'x')
        payloads['MaaLimbus-win-x64.zip']=buffer.getvalue()
        payloads['SHA256SUMS']=(hashlib.sha256(buffer.getvalue()).hexdigest()+'  MaaLimbus-win-x64.zip\n').encode()
        for asset in release['assets']:
            data=payloads[asset['name']];asset.update(size=len(data),digest='sha256:'+hashlib.sha256(data).hexdigest())
    result=stage_release(release,tmp_path/'updates',transport=offline(payloads))
    assert result['status']=='failed' and not result['installed']
    assert not list(Path(result['stage']).glob('*.part'))


def test_partial_failure_scrubs_secrets_persists_deadline_and_defers_restart(tmp_path):
    release,_=fixture();cache=tmp_path/'state.json';calls=[]
    def fail(url,path,*args):
        calls.append(url);Path(path).write_bytes(b'partial')
        raise urllib.error.HTTPError(url,429,'secret proxy password',{'Retry-After':'600'},None)
    result=stage_release(release,tmp_path/'updates',transport=fail,cache=cache)
    assert result['status']=='failed' and not list(Path(result['stage']).glob('*.part'))
    assert GitHubState.load(cache).status=='rate_limited'
    assert 'secret' not in (cache.read_text()+(Path(result['stage'])/'stage-result.json').read_text())
    assert stage_release(release,tmp_path/'updates',transport=fail,cache=cache)['status']=='deferred'
    assert len(calls)==1


def test_deadline_failure_has_no_ready_package(tmp_path):
    release,_=fixture()
    def fail(*args):raise TimeoutError('secret')
    result=stage_release(release,tmp_path,transport=fail)
    assert result['status']=='failed' and result['reason']=='deadline' and 'package' not in result


@pytest.mark.parametrize('name', ['CON.txt','folder/NUL','file:stream','one./x','one /x','bad?name', 'one\x01'])
def test_windows_hostile_archive_prevalidation(tmp_path,name):
    archive=tmp_path/'input.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr(name,b'x')
    with pytest.raises(ValueError):extract_checked(archive,tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_archive_file_directory_collision_and_existing_destination(tmp_path):
    archive=tmp_path/'input.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('one',b'x');z.writestr('ONE/file',b'x')
    with pytest.raises(ValueError):extract_checked(archive,tmp_path/'output')
    assert not (tmp_path/'output').exists()
    target=tmp_path/'existing';target.mkdir();(target/'keep').write_text('keep')
    with pytest.raises(ValueError):extract_checked(archive,target)
    assert (target/'keep').read_text()=='keep'


@pytest.mark.parametrize('url', ['http://github.com/file','https://evil.example/file','https://user:password@github.com/file'])
def test_redirect_cannot_downgrade_or_leave_asset_hosts(url):
    with pytest.raises(StageError):HTTPSRedirect().redirect_request(None,None,302,'',{},url)
