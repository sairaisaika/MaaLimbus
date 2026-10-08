"""Build a new, local Windows development package; never install or publish it."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from maalimbus.archives import extract_checked
from maalimbus.release_package import export_assets
ARCHIVES = {
    'mxu': ('825A62AF7A344A7A47ADCA09D1414128E6F53A222A11CDF456F08D2E83D31724',
            'https://github.com/MistEO/MXU/releases/download/v2.7.1/MXU-win-x86_64-v2.7.1.zip'),
    'maa': ('55DCEE2306F95656949165237E781322F6858A1675A3B271BC045A50F43C41B7',
            'https://github.com/MaaXYZ/MaaFramework/releases/download/v5.12.2/MAA-win-x86_64-v5.12.2.zip'),
    'mxu_source': ('B350877C03598922B14D1804923E331361ACF64534494945274B80B5D28CEC35',
                   'https://github.com/MistEO/MXU/tree/9fa8cc51e8ff8cd89d99f3ea55fe3a7a82e6ede3'),
    'maa_source': ('0013BAAA2F30B14EA6B102A5F1A1438D7CC97A60AAAA5040F755DA711B0A4ACF',
                   'https://github.com/MaaXYZ/MaaFramework/tree/f625a60edeccd4549f9a71c0f74628d827ade8fb'),
}


def digest(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def verify(path, expected):
    if digest(path).upper() != expected:
        raise ValueError(f'Unreviewed archive: {path}')


def copy_public_sources(output):
    # Explicit public roots: never copy build/config/evidence or a previous install.
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('src', 'agent', 'tools', 'tests', 'docs', 'assets', 'THIRD_PARTY_NOTICES'):
            for path in sorted((ROOT/name).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                    archive.write(path, path.relative_to(ROOT).as_posix())
        for name in ('README.md', 'README_en.md', 'LICENSE', 'pyproject.toml', 'PROJECT.md', '.gitignore'):
            archive.write(ROOT/name, name)


def freeze(entry, name, work):
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
                    '--name', name, '--paths', str(ROOT/'src'), '--paths', str(ROOT/'agent'),
                    '--distpath', str(work/'dist'), '--workpath', str(work/'work'),
                    '--specpath', str(work/'spec'), str(entry)], check=True, timeout=600)
    return work/'dist'/name


def pending_items(*, verified_dungeon_clear):
    """What the package still does not claim, in one place.

    The five-floor loop only leaves the list when the caller passes
    --verified-dungeon-clear, which also hashes the acceptance record into
    build-info.json: an unproven claim about the live game is worse than a listed
    gap.
    """
    pending = ['MXU UI validation', 'live input postcondition',
               'artwork redistribution rights',
               'complete native dependency source/notices release audit']
    if not verified_dungeon_clear:
        pending.insert(0, 'full five-floor loop')
    return pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ARCHIVES:
        parser.add_argument('--'+key.replace('_', '-'), type=Path, required=True)
    parser.add_argument('--verified-dungeon-clear', action='store_true',
                        help='the live acceptance run cleared five floors, claimed the '
                             'rewards and re-entered; only pass it with that evidence')
    parser.add_argument('--clear-evidence', type=Path, default=ROOT/'docs/acceptance.md',
                        help='the acceptance record hashed into build-info when the clear '
                             'is claimed')
    args = parser.parse_args()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise ValueError('Commit the source before building a release candidate')
    if args.clear_evidence is not None and not args.clear_evidence.is_file():
        raise ValueError(f'Missing acceptance record: {args.clear_evidence}')
    inputs = {key: getattr(args, key).resolve() for key in ARCHIVES}
    for key, path in inputs.items():
        verify(path, ARCHIVES[key][0])
    stage = ROOT/'build'/('windows-package-'+uuid.uuid4().hex)
    stage.mkdir(parents=True)
    for key in ('mxu', 'maa'):
        extract_checked(inputs[key], stage/key)
    for original, notice in [('maa/LICENSE.md', 'MaaFramework-LGPL-3.0.md'),
                              ('mxu/LICENSE', 'MXU-AGPL-3.0.txt')]:
        if (stage/original).read_text(encoding='utf-8') != (ROOT/'THIRD_PARTY_NOTICES'/notice).read_text(encoding='utf-8'):
            raise ValueError(f'Runtime license differs from retained notice: {notice}')
    app = stage/'MaaLimbus-win-x64'
    app.mkdir()
    shutil.copyfile(stage/'mxu/mxu.exe', app/'MaaLimbus.exe')
    shutil.copytree(stage/'maa/bin', app/'maafw')
    for name in ('assets', 'docs', 'THIRD_PARTY_NOTICES'):
        shutil.copytree(ROOT/name, app/name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('README.md', 'README_en.md', 'LICENSE'):
        shutil.copyfile(ROOT/name, app/name)
    shutil.copyfile(stage/'mxu/LICENSE', app/'THIRD_PARTY_NOTICES/MXU-AGPL-3.0.txt')
    for entry, name, target in [('agent/main.py', 'MaaLimbusAgent', 'agent'),
                                ('tools/run_native.py', 'MaaLimbusRunner', 'runner'),
                                ('tools/launch_app.py', 'MaaLimbusLauncher', 'launcher')]:
        shutil.copytree(freeze(ROOT/entry, name, stage/name), app/target)
    interface = json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    interface['agent'] = {'child_exec': './agent/MaaLimbusAgent.exe', 'child_args': []}
    interface['license'] = './LICENSE'
    interface['icon'] = 'assets/' + interface['icon']
    interface['welcome'] = './README.md'
    interface['languages'] = {k:'assets/'+v for k,v in interface['languages'].items()}
    for resource in interface['resource']:
        resource['path'] = [p.replace('./resource/', './assets/resource/') for p in resource['path']]
    (app/'interface.json').write_text(json.dumps(interface, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (app/'sources').mkdir()
    shutil.copyfile(inputs['mxu_source'], app/'sources/MXU-v2.7.1-source.zip')
    shutil.copyfile(inputs['maa_source'], app/'sources/MaaFramework-v5.12.2-source.zip')
    copy_public_sources(app/'sources/MaaLimbus-source.zip')
    result = subprocess.run([str(app/'agent/MaaLimbusAgent.exe'), '--self-test'],
                            cwd=stage, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Packaged Agent self-test failed: '+result.stderr)
    self_test = json.loads(result.stdout.strip())
    if Path(self_test['application_root']) != app or not self_test['passed']:
        raise RuntimeError('Packaged Agent resolved the wrong resource directory')
    subprocess.run([str(app/'runner/MaaLimbusRunner.exe'), '--help'], cwd=stage,
                   capture_output=True, check=True, timeout=30)
    pending = pending_items(verified_dungeon_clear=args.verified_dungeon_clear)
    info = {'project':'MaaLimbus', 'development_only':True,
            'verified_dungeon_clear':bool(args.verified_dungeon_clear),
            'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'source_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
            'built_at':datetime.now(timezone.utc).isoformat(), 'self_test':self_test,
            'inputs':{k:{'sha256':digest(path),'source':ARCHIVES[k][1]} for k,path in inputs.items()},
            'mxu_modified':False, 'maa_modified':False,
            'pending':pending}
    if args.verified_dungeon_clear:
        # The claim is only as good as the record it points at, so hash that record.
        info['clear_evidence'] = {'path':str(args.clear_evidence.resolve()),
                                  'sha256':digest(args.clear_evidence)}
    (app/'build-info.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest = {p.relative_to(app).as_posix():digest(p) for p in sorted(app.rglob('*'))
                if p.is_file() and 'evidence' not in p.relative_to(app).parts}
    (app/'package-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    # Verification can create empty evidence dirs. No private runtime data enters the zip.
    record = dict(app=str(app), self_test=self_test,
                  **export_assets(app, stage/'release-assets'))
    (ROOT/'build/windows-package-latest.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__ == '__main__':
    main()
