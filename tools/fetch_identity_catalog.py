"""Build the committed identity catalog from community static data (bounded reads).

Two community mirrors of game data are read through `github_cache.GitHubState`,
so every request carries an ETag, a bounded retry deadline and a cached body
that survives restarts. Raw payloads stay under `build/upstream/`; only derived
facts (ids, names, numbers, keyword tags) reach `assets/resource/base/`.

    python tools/fetch_identity_catalog.py --check
    python tools/fetch_identity_catalog.py --refresh
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from maalimbus.github_cache import GitHubState
from maalimbus.identity_catalog import merge
from maalimbus.storage import write_json

STATIC_REPO = 'flaglow/LimbusStaticData'
LLC_REPO = 'LocalizeLimbusCompany/LocalizeLimbusCompany'
STATIC_ROOT = 'StaticData/static-data'
LLC_ROOT = 'LLC_zh-CN'
USER_AGENT = 'maalimbus-identity-catalog'


def raw_url(repo, revision, path):
    return 'https://raw.githubusercontent.com/%s/%s/%s' % (repo, revision, path)


def state_path(directory, repo, path):
    stem = Path(path).name
    digest = hashlib.sha1(('%s/%s' % (repo, path)).encode()).hexdigest()[:12]
    return directory/(digest + '-' + stem + '.json')


def fetch_json(url, path, *, refresh=False, now=None):
    """Conditional GET with the cached body; returns (payload, status)."""
    now = time.time() if now is None else now
    state = GitHubState.load(path)
    if state.payload is not None and not refresh and state.due(now):
        return state.payload, state.status
    if state.payload is not None and not refresh and not state.due(now):
        return state.payload, state.status
    headers = {'User-Agent': USER_AGENT}
    if state.etag and not refresh:
        headers['If-None-Match'] = state.etag
    body = None
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=90) as response:
            code, raw, response_headers = response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as error:
        code, raw, response_headers = error.code, error.read(), dict(error.headers)
    except (urllib.error.URLError, TimeoutError) as error:
        state.failures += 1
        state.status = 'network_error'
        state.retry_at = now + min(3600, 30*2**min(state.failures - 1, 7))
        state.save(path)
        raise RuntimeError('%s: %s' % (url, error))
    if code == 200:
        body = json.loads(raw)
    state.response(code, response_headers, body, now)
    state.save(path)
    return state.payload, state.status


def resolve_commit(repo, directory, *, refresh=False, override=None):
    """(sha, commit date, status) for the repository default branch."""
    if override:
        return override, '', 'pinned'
    url = 'https://api.github.com/repos/%s/commits/main' % repo
    payload, status = fetch_json(url, state_path(directory, repo, 'commits-main.json'),
                                 refresh=refresh)
    if isinstance(payload, dict) and isinstance(payload.get('sha'), str):
        date = (payload.get('commit') or {}).get('committer', {}).get('date', '')
        return payload['sha'], date, status
    return None, '', status


def plan_files():
    """(repo, path) pairs the catalog needs."""
    files = [(LLC_REPO, LLC_ROOT + '/' + name) for name in
             ('Personalities.json', 'BattleKeywords.json', 'UnitKeyword.json')]
    for index in range(1, 13):
        number = '%02d' % index
        files.append((STATIC_REPO,
                      '%s/personality/personality-%s/personality-%s.json' % (STATIC_ROOT, number, number)))
        files.append((STATIC_REPO,
                      '%s/skill/personality-skill-%s/personality-skill-%s.json' % (STATIC_ROOT, number, number)))
    return files


def data_list(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('dataList'), list):
        raise ValueError('expected a dataList payload')
    return payload['dataList']


def static_list(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('list'), list):
        raise ValueError('expected a list payload')
    return payload['list']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'assets/resource/base/identity-catalog.json')
    parser.add_argument('--state', type=Path, default=ROOT/'build/upstream/state')
    parser.add_argument('--refresh', action='store_true', help='ignore cached deadlines')
    parser.add_argument('--check', action='store_true', help='fetch and report status without writing')
    parser.add_argument('--commit', action='append', default=[],
                        help='override a revision, e.g. --commit flaglow/LimbusStaticData=<sha>')
    args = parser.parse_args()
    overrides = {}
    for item in args.commit:
        repo, _, revision = item.partition('=')
        if not repo or not revision:
            raise SystemExit('--commit needs <owner/repo>=<sha>')
        overrides[repo] = revision
    args.state.mkdir(parents=True, exist_ok=True)
    statuses = {}
    commits = {}
    dates = {}
    for repo in (STATIC_REPO, LLC_REPO):
        revision, date, status = resolve_commit(
            repo, args.state, refresh=args.refresh, override=overrides.get(repo))
        commits[repo] = revision
        dates[repo] = date
        statuses['commit:' + repo] = status
    payloads = {}
    for repo, path in plan_files():
        revision = commits.get(repo)
        if not revision:
            raise SystemExit('Cannot resolve a revision for %s (status %s); retry later or pass --commit'
                             % (repo, statuses.get('commit:' + repo)))
        payload, status = fetch_json(raw_url(repo, revision, path), state_path(args.state, repo, path),
                                    refresh=args.refresh)
        statuses[path.split('/')[-1]] = status
        if payload is None:
            raise SystemExit('%s is unavailable (status %s)' % (path, status))
        payloads[(repo, path)] = payload
    names = {}
    for item in data_list(payloads[(LLC_REPO, LLC_ROOT + '/Personalities.json')]):
        if isinstance(item, dict) and isinstance(item.get('id'), int):
            names[item['id']] = {'name': item.get('name', ''), 'title': item.get('title', '')}
    units = {}
    for item in data_list(payloads[(LLC_REPO, LLC_ROOT + '/UnitKeyword.json')]):
        if isinstance(item, dict) and isinstance(item.get('id'), str):
            units[item['id']] = item.get('content', '')
    personalities, skills = [], []
    for index in range(1, 13):
        number = '%02d' % index
        personalities.extend(static_list(payloads[(STATIC_REPO,
            '%s/personality/personality-%s/personality-%s.json' % (STATIC_ROOT, number, number))]))
        skills.extend(static_list(payloads[(STATIC_REPO,
            '%s/skill/personality-skill-%s/personality-skill-%s.json' % (STATIC_ROOT, number, number))]))
    catalog = merge(personalities, skills, names, units,
                    source=['https://github.com/' + STATIC_REPO, 'https://github.com/' + LLC_REPO],
                    commit={repo: revision for repo, revision in commits.items() if revision})
    catalog['commit_date'] = {repo: date for repo, date in dates.items() if date}
    catalog['coverage'] = {
        'identities': len(catalog['identities']),
        'with_keywords': sum(1 for i in catalog['identities'] if i['keywords']),
        'note': ('Offline roster facts only. The statics mirror lags the live game, so this '
                 'catalog must not be treated as the list of currently owned identities: the '
                 'in-game identity filter remains the authority for what a player owns now.'),
    }
    catalog['note'] = ('Derived facts only (ids, names, rank, HP, resistances, keyword tags); '
                       'raw community payloads stay in build/upstream and are not committed.')
    if args.check:
        print(json.dumps({'check': True, 'identities': len(catalog['identities']),
                          'statuses': statuses, 'commits': commits}, ensure_ascii=False, indent=2))
        return
    write_json(args.output, catalog)
    summary = {'identities': len(catalog['identities']),
               'with_keywords': sum(1 for i in catalog['identities'] if i['keywords']),
               'named': sum(1 for i in catalog['identities'] if i['name']),
               'output': str(args.output.relative_to(ROOT)),
               'commits': commits,
               'statuses': statuses}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
