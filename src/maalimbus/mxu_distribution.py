"""Validate a local modified MXU artifact with its complete source companion."""
import hashlib
import json
from pathlib import Path
import zipfile

def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def validate_artifact(exe,proof_path,root):
    exe,proof_path,root=Path(exe),Path(proof_path),Path(root)
    proof=json.loads(proof_path.read_text(encoding='utf8'))
    source=proof_path.parent/'MXU-MaaLimbus-source.zip'
    if (proof.get('version')!=1 or proof.get('native_build') is not True or
        proof.get('upstream_commit')!='9fa8cc51e8ff8cd89d99f3ea55fe3a7a82e6ede3' or
        proof.get('upstream_sha256')!='b350877c03598922b14d1804923e331361acf64534494945274b80b5d28cec35' or
        digest(exe)!=proof.get('exe_sha256') or digest(source)!=proof.get('source_sha256')):
        raise ValueError('Modified MXU artifact identity mismatch')
    current={p.relative_to(root).as_posix():digest(p) for p in (root/'desktop/mxu').iterdir() if p.is_file()}
    if current!=proof.get('overlays') or digest(root/'tools/patch_mxu_client.py')!=proof.get('patch_sha256'):
        raise ValueError('Modified MXU artifact is stale')
    with zipfile.ZipFile(source) as z:
        members={n.removeprefix('MXU-2.7.1/'):hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
    if members!=proof.get('source_manifest') or not members:
        raise ValueError('Modified MXU corresponding source mismatch')
    return source,proof
