"""Download and inspect an update in a new directory; never install or execute it."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
import uuid

from .archives import extract_checked, safe_name
from .github_cache import GitHubState
from .storage import write_json


class StageError(ValueError):
    pass


def select_assets(release, repo):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise StageError('Invalid repository')
    if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
        raise StageError('A stable published release is required')
    tag = release.get('tag_name', '')
    if not isinstance(tag, str) or not re.fullmatch(r'v?\d+\.\d+\.\d+', tag):
        raise StageError('Unsupported release tag')
    assets = release.get('assets')
    if not isinstance(assets, list):
        raise StageError('Missing release assets')
    packages = [a for a in assets if isinstance(a, dict) and a.get('name') in
                ('MaaLimbus-win-x64.zip', f'MaaLimbus-win-x64-{tag}.zip')]
    if len(packages) != 1:
        raise StageError('Exactly one Windows package is required')
    package = packages[0]
    sums = [a for a in assets if isinstance(a, dict) and a.get('name') in
            ('SHA256SUMS', package['name']+'.sha256')]
    if len(sums) != 1:
        raise StageError('Exactly one checksum asset is required')
    for asset, limit in ((package, 700_000_000), (sums[0], 65536)):
        size = asset.get('size')
        if type(size) is not int or not 0 < size <= limit:
            raise StageError('Invalid or excessive asset size')
        name = asset['name']
        expected = f'https://github.com/{repo}/releases/download/{tag}/{name}'
        if asset.get('browser_download_url') != expected:
            raise StageError('Asset URL does not belong to the selected release')
        digest = asset.get('digest')
        if digest is not None and not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', str(digest)):
            raise StageError('Invalid GitHub asset digest')
    return tag, package, sums[0]


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if (parsed.scheme != 'https' or parsed.hostname not in
                ('github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com')
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise StageError('Untrusted asset redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, path, size, deadline, proxy=None):
    handlers = [HTTPSRedirect(), urllib.request.ProxyHandler({'https': proxy} if proxy else {})]
    opener = urllib.request.build_opener(*handlers)
    remaining = deadline-time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Update deadline reached')
    request = urllib.request.Request(url, headers={'User-Agent':'MaaLimbus/0.1.0'})
    with opener.open(request, timeout=min(12, remaining)) as response, Path(path).open('xb') as output:
        length = response.headers.get('Content-Length')
        if length is not None and int(length) != size:
            raise StageError('Asset length differs from release metadata')
        total = 0
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('Update deadline reached')
            chunk = response.read(min(65536, size-total+1))
            if not chunk:
                break
            total += len(chunk)
            if total > size:
                raise StageError('Asset exceeds declared size')
            output.write(chunk)
        if total != size:
            raise StageError('Incomplete asset download')


def file_digest(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def checksum_for(path, name):
    if Path(path).stat().st_size > 65536:
        raise StageError('Checksum file is too large')
    matches = []
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        m = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?(.+)', line.strip())
        if m and m[2] == name:
            matches.append(m[1].lower())
    if len(matches) != 1:
        raise StageError('Package checksum missing or duplicated')
    return matches[0]


def verify_package(app):
    """A package manifest must cover every file and contain no private runtime roots."""
    app = Path(app)
    manifest_path = app/'package-manifest.json'
    if not manifest_path.is_file() or manifest_path.stat().st_size > 4*1024*1024:
        raise StageError('Missing or oversized package manifest')
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise StageError('Duplicate manifest key')
            result[key] = value
        return result
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'), object_pairs_hook=unique)
    if not isinstance(manifest, dict) or not manifest or len(manifest) > 20000:
        raise StageError('Invalid package manifest')
    required = {'MaaLimbus.exe', 'interface.json', 'LICENSE', 'build-info.json',
                'agent/MaaLimbusAgent.exe', 'runner/MaaLimbusRunner.exe'}
    if not required <= manifest.keys():
        raise StageError('Incomplete Windows package')
    seen = set()
    for name, digest in manifest.items():
        if not isinstance(name, str) or safe_name(name) != name:
            raise StageError('Invalid manifest path')
        parts = Path(name).parts
        if parts[0].casefold() in ('config', 'evidence', 'build', 'logs'):
            raise StageError('Private runtime data in update package')
        if name.casefold() in seen or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
            raise StageError('Duplicate path or invalid manifest hash')
        seen.add(name.casefold())
        file = app/name
        if not file.is_file() or file_digest(file) != digest.lower():
            raise StageError('Package file hash differs from manifest')
    actual = {p.relative_to(app).as_posix() for p in app.rglob('*') if p.is_file()}
    if actual != set(manifest) | {'package-manifest.json'}:
        raise StageError('Unlisted or missing package files')
    return len(manifest)


def stage_release(release, root, repo='sairaisaika/MaaLimbus', *, proxy=None,
                  transport=download, timeout=120, cache=None):
    if not 1 <= timeout <= 300:
        raise StageError('Update timeout must be 1..300 seconds')
    if proxy and not re.fullmatch(r'https?://[^\s]+', proxy):
        raise StageError('HTTP(S) proxy required')
    if cache is not None:
        state = GitHubState.load(Path(cache))
        if state.status in ('rate_limited', 'network_error', 'access_denied') and not state.due(time.time()):
            return {'status':'deferred', 'retry_at':state.retry_time(), 'installed':False}
    tag, package, sums = select_assets(release, repo)
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    stage = root/('update-'+uuid.uuid4().hex)
    stage.mkdir()
    deadline = time.monotonic()+timeout
    result = {'status':'failed', 'stage':str(stage), 'version':tag,
              'installed':False, 'executed':False,
              'created_at':datetime.now(timezone.utc).isoformat()}
    try:
        for asset in (sums, package):
            partial = stage/(asset['name']+'.part')
            transport(asset['browser_download_url'], partial, asset['size'], deadline, proxy)
            if not partial.is_file() or partial.stat().st_size != asset['size']:
                raise StageError('Incomplete asset download')
            actual = file_digest(partial)
            if asset.get('digest') and actual != asset['digest'][7:].lower():
                raise StageError('GitHub asset digest mismatch')
            partial.rename(stage/asset['name'])
        expected = checksum_for(stage/sums['name'], package['name'])
        if file_digest(stage/package['name']) != expected:
            raise StageError('Downloaded package checksum mismatch')
        if time.monotonic() >= deadline:
            raise TimeoutError('Update deadline reached')
        app = stage/'package'
        extract_checked(stage/package['name'], app)
        count = verify_package(app)
        if time.monotonic() >= deadline:
            raise TimeoutError('Update deadline reached')
        result.update(status='staged', package=str(app), sha256=expected, files=count,
                      pending=['installed process exit', 'backup and rollback installation',
                               'installed version/configuration verification'])
    except Exception as error:
        # Persist only a safe category, never a URL/proxy/exception with credentials.
        result['reason'] = 'deadline' if isinstance(error, TimeoutError) else 'download_or_package_validation_failed'
        if cache is not None and isinstance(error, OSError):
            state = GitHubState.load(Path(cache))
            headers = dict(getattr(error, 'headers', {}) or {})
            state.response(getattr(error, 'code', 0), headers, None, time.time())
            state.save(Path(cache))
            result['retry_at'] = state.retry_time()
        # Delete only partial downloads in the newly created private stage.
        for partial in stage.glob('*.part'):
            if partial.resolve().parent == stage.resolve():
                partial.unlink(missing_ok=True)
    write_json(stage/'stage-result.json', result)
    return result
