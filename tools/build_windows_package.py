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
ARCHIVES = {
    'mxu': ('A2375C171EEB360B7D3E7762FB30CDFB452860D8485FBB5D542AE8A053BE8E7D',
            'https://github.com/MistEO/MXU/releases/download/v2.5.1/MXU-win-x86_64-v2.5.1.zip'),
    'maa': ('55DCEE2306F95656949165237E781322F6858A1675A3B271BC045A50F43C41B7',
            'https://github.com/MaaXYZ/MaaFramework/releases/download/v5.12.2/MAA-win-x86_64-v5.12.2.zip'),
    'mxu_source': ('9DBD168F01F6A74E28B79949E8FDC735BFB8DDE666C5EC8D6409D821A5519B6E',
                   'https://github.com/MistEO/MXU/tree/fb05f97fde0c112e3e07740a385072638a24ba48'),
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ARCHIVES:
        parser.add_argument('--'+key.replace('_', '-'), type=Path, required=True)
    args = parser.parse_args()
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
                                ('tools/run_native.py', 'MaaLimbusRunner', 'runner')]:
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
    shutil.copyfile(inputs['mxu_source'], app/'sources/MXU-v2.5.1-source.zip')
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
    info = {'project':'MaaLimbus', 'development_only':True, 'verified_dungeon_clear':False,
            'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'source_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
            'built_at':datetime.now(timezone.utc).isoformat(), 'self_test':self_test,
            'inputs':{k:{'sha256':digest(path),'source':ARCHIVES[k][1]} for k,path in inputs.items()},
            'mxu_modified':False, 'maa_modified':False,
            'pending':['MXU UI validation','live input postcondition','full five-floor loop',
                       'artwork redistribution rights','complete native dependency source/notices release audit']}
    (app/'build-info.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest = {p.relative_to(app).as_posix():digest(p) for p in sorted(app.rglob('*'))
                if p.is_file() and 'evidence' not in p.relative_to(app).parts}
    (app/'package-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    # Verification can create empty evidence dirs. No private runtime data enters the zip.
    archive = stage/'MaaLimbus-win-x64-development.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
        for name in [*manifest, 'package-manifest.json']:
            output.write(app/name, name)
    record = {'app':str(app),'archive':str(archive),'sha256':digest(archive),
              'files':len(manifest),'self_test':self_test,'published':False}
    (ROOT/'build/windows-package-latest.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__ == '__main__':
    main()
