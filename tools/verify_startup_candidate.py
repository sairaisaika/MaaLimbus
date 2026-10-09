"""Run actual newer-version startup update with retained offline release bytes.

No public GitHub claim, GUI launch, desktop replacement or game input.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.releases import ReleaseClient
from maalimbus.startup_update import startup_update
from maalimbus.storage import write_json
from maalimbus.update_install import install_staged,metadata,PRIVATE,private_hashes
from maalimbus.update_stage import stage_release,file_digest


def main():
    record=json.loads((ROOT/'build/windows-package-latest.json').read_text())
    archive=Path(record['archive'])
    assert file_digest(archive)==record['sha256']
    version=record['version']
    baseline=ROOT/'dist/MaaLimbus'
    before=metadata(baseline)['version']
    assert tuple(map(int,version.lstrip('v').split('.')))>tuple(map(int,before.lstrip('v').split('.')))
    private_before=private_hashes(baseline)
    sandbox=ROOT/'build'/('startup-candidate-'+uuid.uuid4().hex)
    app=sandbox/'app'
    shutil.copytree(baseline,app,ignore=lambda directory,names:[n for n in names
        if Path(directory)==baseline and n in PRIVATE])
    write_json(app/'config/nested/private-sentinel.json',dict(retained=True))
    sums=(record['sha256']+'  '+archive.name+'\n').encode()
    release=dict(tag_name=version,assets=[dict(name=name,size=size,digest='sha256:'+digest,
        browser_download_url=f'https://github.com/sairaisaika/MaaLimbus/releases/download/{version}/{name}')
        for name,size,digest in [(archive.name,archive.stat().st_size,record['sha256']),
            ('SHA256SUMS',len(sums),hashlib.sha256(sums).hexdigest())]])
    metadata_requests=[]
    def release_transport(url,headers,proxy):
        metadata_requests.append(url)
        return 200,{'ETag':'"retained-candidate"'},release
    def asset_transport(url,path,size,deadline,proxy):
        assert proxy is None
        if url.endswith('/SHA256SUMS'):path.write_bytes(sums);return
        assert url.endswith('/'+archive.name)
        with archive.open('rb') as source,path.open('xb') as target:
            while data:=source.read(65536):
                if time.monotonic()>=deadline:raise TimeoutError('Retained asset deadline')
                target.write(data)
    def stage(payload,path,**kwargs):
        return stage_release(payload,path,transport=asset_transport,**kwargs)
    def install(path,target):
        return install_staged(path,target,ROOT/'build/controller.lock')
    factory=lambda path:ReleaseClient(path,transport=release_transport)
    result=startup_update(app,sandbox/'work',client_factory=factory,stage=stage,install=install)
    assert result['installed'] and result['version_before']==before and result['version_after']==version
    assert result['install_proof']['verification']['agent_self_test']
    assert json.loads((app/'config/nested/private-sentinel.json').read_text())=={'retained':True}
    def forbidden(*args,**kwargs):raise AssertionError('Current cached version must not stage/install again')
    again=startup_update(app,sandbox/'work',client_factory=factory,stage=forbidden,install=forbidden)
    assert again['status']=='current' and again['requested'] is False and len(metadata_requests)==1
    assert private_before==private_hashes(baseline)
    output=ROOT/'build/startup-candidate-real-verification.json'
    write_json(output,dict(passed=True,source_commit=record['source_commit'],archive_sha256=record['sha256'],
        install=result,cached_restart_check=again,metadata_fixture_requests=len(metadata_requests),
        isolated_app=str(app),desktop_changed=False,game_input=False,gui_restart_verified=False,
        public_release_verified=False,network_requested=False,scope='actual startup/cache/stage/install; retained offline transports'))
    print(output)


if __name__=='__main__':main()
