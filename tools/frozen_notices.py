"""Retain installed Python distribution notices without claiming a full audit."""
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import sys

DISTRIBUTIONS = ('numpy', 'opencv-python', 'psutil', 'pywin32', 'PyYAML',
                 'maafw', 'pyreadline3', 'pyinstaller')


def collect(output, *, distribution=importlib.metadata.distribution,
            python_root=None):
    output = Path(output)
    records = {}
    pending = []
    for name in DISTRIBUTIONS:
        dist = distribution(name)
        notices = []
        for item in dist.files or ():
            path = PurePosixPath(str(item).replace('\\', '/'))
            # Wheel metadata contains the author's distributed license bundle.
            if not path.parts or not path.parts[0].endswith('.dist-info'):
                continue
            if not any(part.lower().startswith(('license', 'copying', 'notice'))
                       for part in path.parts[1:]):
                continue
            if path.is_absolute() or any(part in ('.', '..') for part in path.parts):
                raise ValueError('Unsafe distribution notice path')
            data = Path(dist.locate_file(item)).read_bytes()
            if not data.strip():
                raise ValueError('Empty distribution notice: '+name)
            target = output / name / Path(*path.parts[1:])
            notices.append((target, data, path.as_posix()))
        if not notices:
            raise ValueError('Missing distribution notices: '+name)
        records[name] = dict(version=dist.version, notices=[])
        for target, data, source in notices:
            pending.append((target, data))
            records[name]['notices'].append(dict(path=target.relative_to(output).as_posix(),
                wheel_member=source, sha256=hashlib.sha256(data).hexdigest()))
    python_root = Path(python_root or sys.base_prefix)
    data = (python_root/'LICENSE.txt').read_bytes()
    if not data.strip():
        raise ValueError('Empty Python license')
    pending.append((output/'Python/LICENSE.txt', data))
    records['Python'] = dict(version=sys.version.split()[0], notices=[dict(
        path='Python/LICENSE.txt', sha256=hashlib.sha256(data).hexdigest())])
    # Validate every source first, then materialize notices in the new stage.
    for target, data in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    proof = dict(components=records, scope='installed build-environment notice bytes',
                 complete_dependency_audit=False, frozen_binary_origin_verified=False)
    (output/'provenance.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
    return proof
