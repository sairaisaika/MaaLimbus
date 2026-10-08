import hashlib
import json
import zipfile

import pytest

from maalimbus.release_package import export_assets
from maalimbus.update_stage import StageError, select_assets, stage_release


def candidate(root, *, dirty=False, private_source=False):
    root.mkdir()
    files = {
        'MaaLimbus.exe': b'mxu', 'LICENSE': b'license',
        'agent/MaaLimbusAgent.exe': b'agent', 'runner/MaaLimbusRunner.exe': b'runner',
        'launcher/MaaLimbusLauncher.exe': b'launcher',
        'interface.json': json.dumps(dict(name='MaaLimbus', interface_version=2,
            version='v0.1.1', github='https://github.com/sairaisaika/MaaLimbus')).encode(),
        'build-info.json': json.dumps(dict(source_dirty=dirty, source_commit='a'*40)).encode(),
    }
    for name, data in files.items():
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (root/'sources').mkdir()
    for name in ('MaaLimbus-source.zip', 'MXU-v2.7.1-source.zip', 'MaaFramework-v5.12.2-source.zip'):
        with zipfile.ZipFile(root/'sources'/name, 'w') as source:
            source.writestr('config/user.json' if private_source else 'src/public.py', 'public')
    manifest(root)


def manifest(root):
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in root.rglob('*') if p.is_file() and p.name != 'package-manifest.json'}
    (root/'package-manifest.json').write_text(json.dumps(files))


def test_exported_assets_are_consumable_by_real_update_stager(tmp_path):
    app = tmp_path/'app'
    candidate(app)
    exported = export_assets(app, tmp_path/'assets')
    assert exported['published'] is False
    payloads = {p.name: p.read_bytes() for p in (tmp_path/'assets').iterdir()}
    release = dict(tag_name=exported['version'], assets=[dict(name=name, size=len(data),
        digest='sha256:'+hashlib.sha256(data).hexdigest(),
        browser_download_url=f'https://github.com/sairaisaika/MaaLimbus/releases/download/v0.1.1/{name}')
        for name, data in payloads.items()])
    select_assets(release, 'sairaisaika/MaaLimbus')
    result = stage_release(release, tmp_path/'stage',
        transport=lambda url, path, *args: path.write_bytes(payloads[url.rsplit('/',1)[1]]))
    assert result['status'] == 'staged'
    assert result['installed'] is False
    assert result['version'] == 'v0.1.1'


@pytest.mark.parametrize('change', ['dirty', 'private_source', 'missing_launcher',
                                  'tampered', 'unlisted_private'])
def test_invalid_candidate_creates_no_release_assets(tmp_path, change):
    app = tmp_path/'app'
    candidate(app, dirty=change=='dirty', private_source=change=='private_source')
    if change=='missing_launcher':
        (app/'launcher/MaaLimbusLauncher.exe').unlink()
        manifest(app)
    if change=='tampered': (app/'agent/MaaLimbusAgent.exe').write_bytes(b'changed')
    if change=='unlisted_private':
        (app/'config').mkdir()
        (app/'config/user-data-root.json').write_text('private')
    with pytest.raises(StageError): export_assets(app, tmp_path/'assets')
    assert not (tmp_path/'assets').exists()


def test_existing_release_assets_are_not_replaced(tmp_path):
    app = tmp_path/'app'
    candidate(app)
    output = tmp_path/'assets'
    output.mkdir()
    (output/'existing').write_text('keep')
    with pytest.raises(FileExistsError): export_assets(app, output)
    assert (output/'existing').read_text() == 'keep'
