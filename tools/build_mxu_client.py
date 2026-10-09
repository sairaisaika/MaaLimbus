"""Build the pinned MXU with project-owned panels and export corresponding source."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.archives import extract_checked
from patch_mxu_client import patch
PIN='9fa8cc51e8ff8cd89d99f3ea55fe3a7a82e6ede3'
UPSTREAM_SHA='b350877c03598922b14d1804923e331361acf64534494945274b80b5d28cec35'

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT/'build/MXU-v2.7.1-source.zip')
    p.add_argument('--work',type=Path,default=ROOT/'build/mxu-interactive-source/MXU-2.7.1')
    p.add_argument('--output',type=Path,default=ROOT/'build/mxu-interactive-artifact')
    a=p.parse_args()
    if sha(a.source)!=UPSTREAM_SHA:raise ValueError('Unknown MXU source archive')
    overlays={f.relative_to(ROOT).as_posix():sha(f) for f in (ROOT/'desktop/mxu').iterdir() if f.is_file()}
    patch_sha=sha(ROOT/'tools/patch_mxu_client.py')
    # Reconstruct expected sources independently; don't bless arbitrary edits in
    # an incremental build directory or include its runtime/preview files.
    with tempfile.TemporaryDirectory(prefix='maalimbus-mxu-') as tmp:
        extract_checked(a.source,Path(tmp)/'source')
        expected=Path(tmp)/'source/MXU-2.7.1'
        patch(expected)
        manifest={f.relative_to(expected).as_posix():sha(f) for f in expected.rglob('*') if f.is_file()}
        a.work.mkdir(parents=True,exist_ok=True)
        for name,digest in manifest.items():
            target=a.work/name
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.is_file() or sha(target)!=digest:shutil.copyfile(expected/name,target)
        # Preview fixtures never enter the production Vite build.
        for name in ('team-preview.html','team-preview.tsx'):
            target=a.work/name
            if target.exists():target.rename(a.work/(name+'.qa-only'))
        subprocess.run(['pnpm.cmd','install','--frozen-lockfile','--ignore-scripts'],cwd=a.work,check=True)
        subprocess.run(['pnpm.cmd','tauri','build','--no-bundle'],cwd=a.work,check=True)
        # Tauri rewrites this TOML while synchronizing features/version, including
        # upstream CRCRLF whitespace. Only semantically identical TOML is allowed;
        # export the actual compiled representation rather than discard its hash.
        cargo='src-tauri/Cargo.toml'
        if sha(a.work/cargo)!=manifest[cargo]:
            if tomllib.loads((a.work/cargo).read_text())!=tomllib.loads((expected/cargo).read_text()):
                raise ValueError('Cargo manifest semantics changed during build')
            shutil.copyfile(a.work/cargo,expected/cargo)
            manifest[cargo]=sha(expected/cargo)
        if any(sha(a.work/name)!=digest for name,digest in manifest.items()):
            raise ValueError('Source changed during build')
        a.output.mkdir(parents=True,exist_ok=True)
        exe=a.output/'mxu.exe'
        shutil.copyfile(a.work/'src-tauri/target/release/mxu.exe',exe)
        source=a.output/'MXU-MaaLimbus-source.zip'
        with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
            for name in sorted(manifest):z.write(expected/name,'MXU-2.7.1/'+name)
        current={f.relative_to(ROOT).as_posix():sha(f) for f in (ROOT/'desktop/mxu').iterdir() if f.is_file()}
        if current!=overlays or sha(ROOT/'tools/patch_mxu_client.py')!=patch_sha:
            raise ValueError('Project overlay changed during build')
        proof=dict(version=1,upstream_commit=PIN,upstream_sha256=UPSTREAM_SHA,
                   exe_sha256=sha(exe),source_sha256=sha(source),overlays=overlays,
                   patch_sha256=patch_sha,native_build=True,
                   ui_verified=False,source_manifest=manifest)
        (a.output/'build-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8')
        print(json.dumps(dict(artifact=str(a.output),exe_sha256=proof['exe_sha256'],native_build=True)))

if __name__=='__main__':main()
