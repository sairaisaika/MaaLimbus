"""GitHub release polling stays independent of the offline game scheduler."""
import json
import re
import time
from pathlib import Path
import urllib.error
import urllib.request
from .github_cache import GitHubState


def request_release(url, headers, proxy=None):
    handler = urllib.request.ProxyHandler({'https':proxy} if proxy else {})
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(url,headers=headers)
    try:
        response = opener.open(request,timeout=12)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw)>2*1024*1024:
            raise ValueError('GitHub response exceeds 2 MiB')
        body = json.loads(raw) if raw else None
        return response.code, dict(response.headers), body


class ReleaseClient:
    def __init__(self,cache:Path,repo='sairaisaika/MaaLimbus',*,proxy=None,transport=request_release):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):
            raise ValueError('Invalid GitHub repository')
        if proxy and not re.fullmatch(r'https?://[^\s]+',proxy):
            raise ValueError('This native HTTP transport requires an HTTP(S) proxy')
        self.cache,self.repo,self.proxy,self.transport=Path(cache),repo,proxy,transport

    def check(self,now=None):
        now = time.time() if now is None else now
        state = GitHubState.load(self.cache)
        if not state.due(now):
            return {'requested':False,'status':state.status,'retry_at':state.retry_time(),
                    'release':state.payload}
        headers={'Accept':'application/vnd.github+json','User-Agent':'MaaLimbus/0.1.0',
                 'X-GitHub-Api-Version':'2022-11-28'}
        if state.etag and state.payload:
            headers['If-None-Match']=state.etag
        try:
            code,response_headers,body=self.transport(
                f'https://api.github.com/repos/{self.repo}/releases/latest',headers,self.proxy)
            if code==200 and (not isinstance(body,dict) or not isinstance(body.get('tag_name'),str)
                              or not isinstance(body.get('assets'),list)):
                raise ValueError('GitHub returned an invalid release')
            state.response(code,response_headers,body,now)
        except (OSError,ValueError,urllib.error.URLError):
            # Never serialize URLs/exceptions: proxy URLs may contain credentials.
            state.response(0,{},None,now)
        state.save(self.cache)
        return {'requested':True,'status':state.status,'retry_at':state.retry_time(),
                'release':state.payload}
