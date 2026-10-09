"""Bind retained MaaDeps runtime bytes to its original development notices."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

RUNTIME_SHA = '3798dbe426054468f2dc6cfbd7513f7983d75275f7a692cdc15e71d3c10074b9'
DEVEL_SHA = '38f0fa67e51b9528f564903055a448da6f2fac0ab843c9defd776a3b372166ee'
COMPONENTS = {'DirectML.dll': 'directml-bin', 'fastdeploy_ppocr_maa.dll': 'maa-fastdeploy',
              'onnxruntime_maa.dll': 'maa-onnxruntime', 'opencv_world4_maa.dll': 'opencv4',
              'ViGEmClient.dll': 'vgamepad-bin'}


def digest(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def collect(runtime, devel, binaries, output):
    runtime, devel, binaries, output = map(Path, (runtime, devel, binaries, output))
    if digest(runtime) != RUNTIME_SHA or digest(devel) != DEVEL_SHA:
        raise ValueError('Unreviewed MaaDeps archive')
    bound = {}
    with tarfile.open(runtime) as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            prefix = 'runtime/maa-x64-windows/'
            if name.startswith(prefix) and name[len(prefix):] in COMPONENTS:
                dll = name[len(prefix):]
                if dll in bound or not member.isfile() or member.size > 128*1024*1024:
                    raise ValueError('Invalid or duplicate dependency runtime member')
                data = archive.extractfile(member).read()
                if data != (binaries/dll).read_bytes():
                    raise ValueError('Dependency runtime bytes differ: '+dll)
                bound[dll] = dict(component=COMPONENTS[dll], sha256=hashlib.sha256(data).hexdigest())
    if set(bound) != set(COMPONENTS):
        raise ValueError('Missing dependency runtime member')
    notices = {}
    with tarfile.open(devel) as archive:
        for member in archive:
            path = PurePosixPath(member.name.removeprefix('./'))
            if not path.as_posix().startswith('vcpkg/installed/maa-x64-windows/share/') or path.name != 'copyright':
                continue
            if len(path.parts) != 6 or any(p in ('.', '..') or ':' in p for p in path.parts):
                raise ValueError('Unsafe dependency notice path')
            component = path.parts[-2]
            if component in notices or not member.isfile() or member.size > 4*1024*1024:
                raise ValueError('Invalid or duplicate dependency notice')
            data = archive.extractfile(member).read()
            if not data.strip():
                raise ValueError('Empty dependency notice')
            notices[component] = (data, path.as_posix())
    if not set(COMPONENTS.values()).issubset(notices):
        raise ValueError('Missing dependency copyright')
    proof = dict(version='v2.12.2', runtime_sha256=RUNTIME_SHA, devel_sha256=DEVEL_SHA,
                 binaries=bound, notices={}, complete_distribution_audit=False,
                 corresponding_dependency_sources_complete=False)
    # Both pinned archives and every bound binary validate before writing notices.
    for component, (data, source) in notices.items():
        target = output/component/'copyright'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        proof['notices'][component] = dict(member=source, path=target.relative_to(output).as_posix(),
            sha256=hashlib.sha256(data).hexdigest())
    (output/'provenance.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
    return proof
