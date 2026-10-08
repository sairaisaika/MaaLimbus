"""Closed-app Windows update transaction; retain backup and fail closed on ambiguity."""
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import uuid

from .controller_lease import ControllerLease
from .storage import write_json
from .update_stage import StageError, file_digest, verify_package

PRIVATE = ('config', 'evidence', 'logs', 'build')


def plain_path(path):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item.exists() and (item.is_symlink() or
                getattr(item.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
            raise StageError('Linked update path rejected')
    return path


def plain_tree(root):
    plain_path(root)
    for item in root.rglob('*'):
        plain_path(item)


def metadata(app, version=None):
    path = app/'interface.json'
    if not path.is_file() or path.stat().st_size > 2*1024*1024:
        raise StageError('Invalid application metadata')
    info = json.loads(path.read_text(encoding='utf-8'))
    if (info.get('name') != 'MaaLimbus' or info.get('interface_version') != 2 or
            not re.fullmatch(r'v?\d+\.\d+\.\d+', str(info.get('version', ''))) or
            info.get('github', '').rstrip('/') != 'https://github.com/sairaisaika/MaaLimbus' or
            (version is not None and info.get('version') != version)):
        raise StageError('Application identity/version mismatch')
    return info


def closed_app(app, *, external_launcher_pid=None):
    """Read CIM identity locally; never print command lines or terminate processes."""
    if os.name != 'nt':
        raise StageError('Windows process verification required')
    script = ('Get-CimInstance Win32_Process | Select-Object ProcessId,Name,ExecutablePath,CommandLine '
              '| ConvertTo-Json -Compress')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, timeout=20)
    if result.returncode or not result.stdout.strip():
        raise StageError('Process identity unavailable')
    records = json.loads(result.stdout)
    if isinstance(records, dict):
        records = [records]
    prefix = str(app).casefold().rstrip('\\/')+'\\'
    for record in records:
        executable = (record.get('ExecutablePath') or '').replace('/', '\\').casefold()
        command = (record.get('CommandLine') or '').replace('/', '\\').casefold()
        # The copied launcher lives outside the installation, but its --app argument
        # names it. Only this process may be excluded; no app/Agent is ignored.
        if external_launcher_pid is not None and record.get('ProcessId') == external_launcher_pid:
            if (external_launcher_pid != os.getpid() or not executable or
                    executable.startswith(prefix)):
                raise StageError('Updater must execute outside the installation')
            continue
        if ((record.get('Name') or '').casefold() in
                ('maalimbus.exe', 'maalimbusagent.exe', 'maalimbusrunner.exe') and not executable):
            raise StageError('Application process identity unavailable')
        if executable.startswith(prefix) or prefix in command:
            raise StageError('Application is still running')


def self_test(app):
    result = subprocess.run([str(app/'agent/MaaLimbusAgent.exe'), '--self-test'], cwd=app,
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise StageError('Installed Agent self-test failed')
    proof = json.loads(result.stdout.strip())
    if (proof.get('passed') is not True or proof.get('device_controller') is not False or
            Path(proof.get('application_root', '')).resolve() != app.resolve()):
        raise StageError('Installed resource root mismatch')
    return {'agent_self_test': True, 'application_root': str(app)}


def private_hashes(app):
    return {p.relative_to(app).as_posix(): file_digest(p)
            for name in PRIVATE if (app/name).exists()
            for p in (app/name).rglob('*') if p.is_file()}


def install_staged(stage, install, controller_lock, *, process_check=closed_app,
                   validator=self_test, lease_factory=ControllerLease):
    """Only a validated stage is eligible. Hooks allow isolated fault-injection tests."""
    stage, install, controller_lock = map(plain_path, (stage, install, controller_lock))
    if (install == Path(install.anchor) or install == Path.home() or
            not install.is_dir() or (install/'.git').exists() or
            install in stage.parents or stage in install.parents or install == stage or
            install in controller_lock.parents):
        raise StageError('Unsafe installation/stage/lock location')
    plain_tree(stage)
    plain_tree(install)
    record = json.loads((stage/'stage-result.json').read_text(encoding='utf-8'))
    package = stage/'package'
    if (record.get('status') != 'staged' or record.get('installed') is not False or
            not re.fullmatch(r'v?\d+\.\d+\.\d+', str(record.get('version', ''))) or
            Path(record.get('package', '')).resolve() != package.resolve()):
        raise StageError('Not a validated update stage')
    verify_package(package)
    new = metadata(package, record.get('version'))
    old = metadata(install)
    version = lambda item: tuple(map(int, item['version'].lstrip('v').split('.')))
    if version(new) < version(old):
        raise StageError('Stable update downgrade rejected')
    for journal in install.parent.glob('.maalimbus-update-*/install-result.json'):
        plain_path(journal)
        prior = json.loads(journal.read_text(encoding='utf-8'))
        if (Path(prior.get('install', '')).resolve() == install.resolve() and
                prior.get('status') in ('preparing', 'swap_pending', 'rollback_failed')):
            raise StageError('Unresolved previous install; inspect retained backup before retry')
    process_check(install)
    work = install.parent/('.maalimbus-update-'+uuid.uuid4().hex)
    work.mkdir()
    candidate, backup = work/'candidate', work/'backup'
    result = {'status': 'preparing', 'installed': False, 'rolled_back': False,
              'version': record['version'], 'install': str(install), 'backup': str(backup),
              'game_input_sent': False, 'ui_verified': False}
    report = work/'install-result.json'
    write_json(report, result)
    lease = lease_factory(controller_lock)
    moved = False
    try:
        # The lease is outside the renamed install, and stays held through verification.
        process_check(install)
        before = private_hashes(install)
        shutil.copytree(package, candidate)
        verify_package(candidate)
        for name in PRIVATE:
            if (install/name).exists():
                shutil.copytree(install/name, candidate/name)
        if private_hashes(candidate) != before:
            raise StageError('Private configuration copy mismatch')
        process_check(install)
        result['status'] = 'swap_pending'
        write_json(report, result)
        install.rename(backup)
        moved = True
        candidate.rename(install)
        metadata(install, record['version'])
        manifest = json.loads((install/'package-manifest.json').read_text(encoding='utf-8'))
        if any(file_digest(install/name) != digest.lower() for name, digest in manifest.items()):
            raise StageError('Installed public file mismatch')
        proof = validator(install)
        if not isinstance(proof, dict) or proof.get('agent_self_test') is not True:
            raise StageError('Installed verification missing')
        if private_hashes(install) != before:
            raise StageError('Private configuration changed during verification')
        result.update(status='installed', installed=True, verification=proof,
                      private_files=len(before), pending=['MXU UI restart/version verification'])
    except Exception:
        result['status'] = 'failed'
        result['reason'] = 'installation_or_verification_failed'
        if moved:
            try:
                if install.exists():
                    install.rename(work/'failed-install')
                backup.rename(install)
                result.update(status='rolled_back', rolled_back=True)
            except OSError:
                result.update(status='rollback_failed', reason='manual_backup_restore_required')
    finally:
        lease.close()
        write_json(report, result)
    return result
