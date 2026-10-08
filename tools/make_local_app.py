"""Assemble the local development app folder from pieces already verified once.

This is the local sibling of tools/build_windows_package.py: it never downloads,
never zips and never publishes. It reuses the MXU executable and the MaaFramework
runtime that a previous, hash-verified package build already extracted, takes the
current assets/ from this working tree, freezes the agent with PyInstaller and
writes the packaged interface.json next to the result.

The point is a folder the user can double-click: MaaLimbus.exe is MXU, the
ProjectInterface V2 GUI, and it must find maafw/ + interface.json + assets/ in its
own directory.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from maalimbus.update_install import plain_path,plain_tree,closed_app,self_test,private_hashes,PRIVATE,metadata
from maalimbus.controller_lease import ControllerLease

# The MXU release this app is assembled from; a renamed copy must match. MXU
# v2.5.1 was pinned first, but it never raised its window on this machine (the
# process stayed alive with no top-level window and no WebView2 children, even
# with the upstream sample project and even outside the harness process tree);
# v2.7.1 loads MaaFramework v5.12.2, shows its window and writes its debug log.
MXU_SHA256 = '1B5487AA2442062A489E20134A82F946F76F57E733A8D8D284C3C76AAF8053E5'
PREPARED = ROOT/'build/windows-package-28e4293e95e847dcb6f335d2b824cc7a/MaaLimbus-win-x64'


def digest(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def packaged_interface():
    """The repository interface.json, rewritten for the flat app layout."""
    interface = json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    interface['agent'] = {'child_exec': './agent/MaaLimbusAgent.exe', 'child_args': []}
    interface['license'] = './LICENSE'
    interface['icon'] = 'assets/' + interface['icon'].replace('./', '')
    interface['welcome'] = './README.md'
    interface['languages'] = {k: 'assets/' + v.replace('./', '')
                              for k, v in interface['languages'].items()}
    for resource in interface['resource']:
        resource['path'] = [p.replace('./resource/', './assets/resource/') for p in resource['path']]
    return interface


def freeze(entry, name, work):
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
                    '--name', name, '--paths', str(ROOT/'src'), '--paths', str(ROOT/'agent'),
                    '--distpath', str(work/'dist'), '--workpath', str(work/'work'),
                    '--specpath', str(work/'spec'), str(entry)], check=True, timeout=900)
    return work/'dist'/name


def replace_local_app(staged,out,*,process_check=closed_app,validator=self_test,
                      lease_factory=ControllerLease):
    staged,out=plain_path(staged),plain_path(out)
    if (out==Path(out.anchor) or out==Path.home() or (out/'.git').exists() or
            out==staged or out in staged.parents or staged in out.parents):
        raise ValueError('Unsafe local app destination')
    plain_tree(staged)
    if out.exists():plain_tree(out)
    lease=lease_factory(ROOT/'build/controller.lock')
    backup=out.parent/(out.name+'.backup-'+uuid.uuid4().hex)
    before={};moved=False
    try:
        process_check(out)
        if out.exists():
            if not (out/'MaaLimbus.exe').is_file():raise ValueError('Not a local MaaLimbus app')
            metadata(out)
            before=private_hashes(out)
            for name in PRIVATE:
                if (out/name).exists():shutil.copytree(out/name,staged/name,dirs_exist_ok=True)
            copied=private_hashes(staged)
            if any(copied.get(name)!=sha for name,sha in before.items()):
                raise ValueError('Local app private copy differs')
            process_check(out)
            out.rename(backup);moved=True
        staged.rename(out)
        proof=validator(out)
        copied=private_hashes(out)
        if not proof.get('agent_self_test') or any(copied.get(name)!=sha for name,sha in before.items()):
            raise ValueError('Installed local app validation failed')
        return dict(backup=str(backup) if moved else None,private_files=len(before),verification=proof)
    except Exception:
        if moved:
            if out.exists():out.rename(out.parent/(out.name+'.failed-'+uuid.uuid4().hex))
            backup.rename(out)
        raise
    finally:
        lease.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mxu-exe', type=Path, default=ROOT/'build/mxu-2.7.1/mxu.exe',
                        help='the MXU executable to rename into MaaLimbus.exe')
    parser.add_argument('--maafw', type=Path, default=PREPARED/'maafw',
                        help='the already-verified MaaFramework runtime directory')
    parser.add_argument('--out', type=Path, default=ROOT/'dist/MaaLimbus')
    parser.add_argument('--skip-agent', action='store_true',
                        help='reuse the frozen agent already in --out instead of freezing again')
    parser.add_argument('--skip-self-test', action='store_true')
    args = parser.parse_args()

    if digest(args.mxu_exe).upper() != MXU_SHA256:
        raise ValueError(f'Unreviewed MXU executable: {args.mxu_exe}')
    if not (args.maafw/'MaaFramework.dll').is_file():
        raise ValueError(f'Missing MaaFramework runtime: {args.maafw}')

    out = plain_path(args.out)
    keep_agent = out/'agent' if args.skip_agent and (out/'agent').is_dir() else None
    # Assemble beside the target and swap at the end: the previous app folder stays
    # usable if the freeze or the self-test fails, and reusing its frozen agent
    # cannot read a directory that was just deleted.
    staged = out.parent/(out.name + '.staging-'+uuid.uuid4().hex)
    staged.mkdir(parents=True)

    shutil.copyfile(args.mxu_exe, staged/'MaaLimbus.exe')
    shutil.copytree(args.maafw, staged/'maafw')
    for name in ('assets', 'docs', 'THIRD_PARTY_NOTICES'):
        shutil.copytree(ROOT/name, staged/name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('README.md', 'README_en.md', 'LICENSE'):
        shutil.copyfile(ROOT/name, staged/name)
    (staged/'interface.json').write_text(
        json.dumps(packaged_interface(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    if keep_agent is not None:
        shutil.copytree(keep_agent, staged/'agent')
    else:
        work = ROOT/'build'/('local-app-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S'))
        shutil.copytree(freeze(ROOT/'agent/main.py', 'MaaLimbusAgent', work), staged/'agent')

    info = {'project': 'MaaLimbus', 'development_only': True, 'packaged_app': False,
            'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)),
            'built_at': datetime.now(timezone.utc).isoformat(),
            'mxu_sha256': digest(staged/'MaaLimbus.exe'),
            'pending': ['MXU UI validation', 'live input postcondition', 'full five-floor loop']}
    if not args.skip_self_test:
        result = subprocess.run([str(staged/'agent/MaaLimbusAgent.exe'), '--self-test'],
                                cwd=staged, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError('Packaged Agent self-test failed: ' + result.stderr)
        info['self_test'] = json.loads(result.stdout.strip())
        if Path(info['self_test']['application_root']).resolve() != staged or not info['self_test']['passed']:
            raise RuntimeError('Packaged Agent resolved the wrong resource directory')
    (staged/'build-info.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    installed=replace_local_app(staged,out)
    print(json.dumps({'app': str(out), 'exe': str(out/'MaaLimbus.exe'),
                      'self_test': info.get('self_test', {}).get('passed'),
                      'installation':installed}, indent=2))


if __name__ == '__main__':
    main()
