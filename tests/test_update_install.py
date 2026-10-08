import hashlib
import json
from pathlib import Path

import pytest

from maalimbus.storage import write_json
from maalimbus.update_install import install_staged
from maalimbus.update_stage import StageError


class Lease:
    def __init__(self, path):
        self.closed = False

    def close(self):
        self.closed = True


def setup(tmp_path):
    old = tmp_path/'app'
    old.mkdir()
    identity = {'name': 'MaaLimbus', 'interface_version': 2,
                'github': 'https://github.com/sairaisaika/MaaLimbus', 'version': 'v0.1.0'}
    write_json(old/'interface.json', identity)
    (old/'MaaLimbus.exe').write_bytes(b'old')
    for name in ('config', 'logs', 'evidence', 'build'):
        (old/name/'nested').mkdir(parents=True)
        (old/name/'nested/private.json').write_bytes(b'private sentinel')
    stage = tmp_path/'stage'
    package = stage/'package'
    package.mkdir(parents=True)
    identity['version'] = 'v0.2.0'
    write_json(package/'interface.json', identity)
    for name in ('MaaLimbus.exe', 'LICENSE', 'build-info.json',
                 'agent/MaaLimbusAgent.exe', 'runner/MaaLimbusRunner.exe'):
        file = package/name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b'new public fixture')
    write_json(package/'package-manifest.json', {
        file.relative_to(package).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in package.rglob('*') if file.is_file()})
    write_json(stage/'stage-result.json', {'status': 'staged', 'installed': False,
                                         'version': 'v0.2.0', 'package': str(package)})
    return stage, old, tmp_path/'controller.lock'


def apply(paths, **kwargs):
    return install_staged(*paths, process_check=lambda app: None,
                          lease_factory=Lease, **kwargs)


def test_real_directory_swap_preserves_nested_private_and_backup(tmp_path):
    paths = setup(tmp_path)
    result = apply(paths, validator=lambda app: {'agent_self_test': True})
    assert result['status'] == 'installed' and result['installed']
    assert not result['ui_verified'] and not result['game_input_sent']
    assert (paths[1]/'MaaLimbus.exe').read_bytes() == b'new public fixture'
    assert (Path(result['backup'])/'MaaLimbus.exe').read_bytes() == b'old'
    for name in ('config', 'logs', 'evidence', 'build'):
        assert (paths[1]/name/'nested/private.json').read_bytes() == b'private sentinel'


@pytest.mark.parametrize('failure', ['throw', 'false', 'private_write'])
def test_failed_installed_validation_restores_old_application(tmp_path, failure):
    paths = setup(tmp_path)
    def validate(app):
        if failure == 'throw':
            raise RuntimeError('secret diagnostic must not be persisted')
        if failure == 'private_write':
            (app/'config/nested/private.json').write_text('changed')
            return {'agent_self_test': True}
        return {'agent_self_test': False}
    result = apply(paths, validator=validate)
    assert result['status'] == 'rolled_back' and result['rolled_back']
    assert not result['installed']
    assert (paths[1]/'MaaLimbus.exe').read_bytes() == b'old'
    assert (paths[1]/'config/nested/private.json').read_bytes() == b'private sentinel'
    assert 'secret' not in json.dumps(result)


def test_active_process_blocks_before_any_swap(tmp_path):
    paths = setup(tmp_path)
    def busy(app):
        raise StageError('Application is still running')
    with pytest.raises(StageError):
        install_staged(*paths, process_check=busy, lease_factory=Lease)
    assert not list(tmp_path.glob('.maalimbus-update-*'))
    assert (paths[1]/'MaaLimbus.exe').read_bytes() == b'old'


@pytest.mark.parametrize('fault', ['hash', 'identity', 'version', 'source_checkout', 'lock_inside', 'downgrade', 'unfinished'])
def test_invalid_stage_or_install_never_replaces_old_files(tmp_path, fault):
    stage, old, lock = setup(tmp_path)
    if fault == 'hash':
        (stage/'package/MaaLimbus.exe').write_bytes(b'tampered')
    if fault == 'identity':
        write_json(old/'interface.json', {'name': 'AnotherApp'})
    if fault == 'version':
        record = json.loads((stage/'stage-result.json').read_text())
        record['version'] = 'v9.0.0'
        write_json(stage/'stage-result.json', record)
    if fault == 'source_checkout':
        (old/'.git').mkdir()
    if fault == 'lock_inside':
        lock = old/'build/controller.lock'
    if fault == 'downgrade':
        info = json.loads((old/'interface.json').read_text())
        info['version'] = 'v3.0.0'
        write_json(old/'interface.json', info)
    if fault == 'unfinished':
        write_json(tmp_path/'.maalimbus-update-unfinished/install-result.json',
                   {'install': str(old), 'status': 'swap_pending'})
    with pytest.raises(StageError):
        apply((stage, old, lock), validator=lambda app: {'agent_self_test': True})
    assert (old/'MaaLimbus.exe').read_bytes() == b'old'


def test_linked_private_directory_is_rejected(tmp_path):
    paths = setup(tmp_path)
    outside = tmp_path/'outside'
    outside.mkdir()
    try:
        (paths[1]/'config/linked').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Host lacks symlink permission')
    with pytest.raises(StageError):
        apply(paths, validator=lambda app: {'agent_self_test': True})
    assert (paths[1]/'MaaLimbus.exe').read_bytes() == b'old'


def test_real_controller_lock_blocks_installation(tmp_path):
    import os
    if os.name != 'nt':
        pytest.skip('Windows lock')
    from maalimbus.controller_lease import ControllerLease
    paths = setup(tmp_path)
    lease = ControllerLease(paths[2])
    try:
        with pytest.raises(OSError):
            install_staged(*paths, process_check=lambda app: None,
                           validator=lambda app: {'agent_self_test': True})
        assert (paths[1]/'MaaLimbus.exe').read_bytes() == b'old'
    finally:
        lease.close()
