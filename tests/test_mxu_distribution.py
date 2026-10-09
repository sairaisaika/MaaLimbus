import hashlib
import json
import zipfile
import pytest
from maalimbus.mxu_distribution import digest,validate_artifact

def artifact(tmp_path):
    root=tmp_path/'repo';(root/'desktop/mxu').mkdir(parents=True);(root/'tools').mkdir()
    (root/'desktop/mxu/TeamBuildEditor.tsx').write_text('editor')
    (root/'tools/patch_mxu_client.py').write_text('patch')
    out=tmp_path/'artifact';out.mkdir();exe=out/'mxu.exe';exe.write_bytes(b'compiled')
    source=out/'MXU-MaaLimbus-source.zip'
    with zipfile.ZipFile(source,'w') as z:z.writestr('MXU-2.7.1/src/editor.tsx','editor')
    proof=dict(version=1,native_build=True,upstream_commit='9fa8cc51e8ff8cd89d99f3ea55fe3a7a82e6ede3',
      upstream_sha256='b350877c03598922b14d1804923e331361acf64534494945274b80b5d28cec35',
      exe_sha256=digest(exe),source_sha256=digest(source),
      overlays={'desktop/mxu/TeamBuildEditor.tsx':digest(root/'desktop/mxu/TeamBuildEditor.tsx')},
      patch_sha256=digest(root/'tools/patch_mxu_client.py'),
      source_manifest={'src/editor.tsx':hashlib.sha256(b'editor').hexdigest()})
    p=out/'build-proof.json';p.write_text(json.dumps(proof))
    return root,exe,p,source

def test_compiled_editor_requires_unchanged_source_companion(tmp_path):
    root,exe,proof,source=artifact(tmp_path)
    assert validate_artifact(exe,proof,root)[0]==source
    source.write_bytes(b'changed')
    with pytest.raises(ValueError,match='identity'):validate_artifact(exe,proof,root)

@pytest.mark.parametrize('target',['exe','overlay','patch'])
def test_changed_binary_or_editor_cannot_be_installed(tmp_path,target):
    root,exe,proof,_=artifact(tmp_path)
    path={'exe':exe,'overlay':root/'desktop/mxu/TeamBuildEditor.tsx','patch':root/'tools/patch_mxu_client.py'}[target]
    path.write_bytes(b'changed')
    with pytest.raises(ValueError):validate_artifact(exe,proof,root)
