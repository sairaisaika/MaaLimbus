"""Export updater-compatible assets from an already verified public package."""
import json
from pathlib import Path
import zipfile

from .update_install import metadata, plain_tree
from .update_stage import verify_package, file_digest, StageError


def export_assets(app, destination):
    app, destination = Path(app), Path(destination)
    plain_tree(app)
    count = verify_package(app)
    identity = metadata(app)
    info = json.loads((app / 'build-info.json').read_text(encoding='utf-8'))
    if info.get('source_dirty') is not False:
        raise StageError('Release candidate requires a clean source revision')
    for name in ('launcher/MaaLimbusLauncher.exe', 'sources/MaaLimbus-source.zip',
                 'sources/MXU-v2.7.1-source.zip', 'sources/MaaFramework-v5.12.2-source.zip'):
        if not (app / name).is_file():
            raise StageError('Missing launcher or corresponding source')
    # Inspect the nested project source too; a clean outer manifest does not
    # establish that its source archive omitted runtime state.
    with zipfile.ZipFile(app / 'sources/MaaLimbus-source.zip') as source:
        for name in source.namelist():
            parts = name.replace('\\', '/').split('/')
            if parts[0].casefold() in ('config', 'evidence', 'build', 'logs', 'dist'):
                raise StageError('Private state in corresponding source archive')
    destination.mkdir(parents=True, exist_ok=False)
    archive = destination / f'MaaLimbus-win-x64-{identity["version"]}.zip'
    # The manifest is checked immediately before export; include every public
    # member, including the manifest itself, with installation-relative paths.
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as output:
        for file in sorted(app.rglob('*')):
            if file.is_file():
                output.write(file, file.relative_to(app).as_posix())
    digest = file_digest(archive)
    sums = destination / 'SHA256SUMS'
    sums.write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    return dict(archive=str(archive), checksum=str(sums), sha256=digest,
                version=identity['version'], source_commit=info.get('source_commit'),
                files=count, published=False)
