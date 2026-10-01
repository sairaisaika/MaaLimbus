"""Bounded GitHub request state. Rate-limit waits survive app restarts."""
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from .storage import read_json, write_json


@dataclass
class GitHubState:
    etag: str = ''
    retry_at: float = 0
    failures: int = 0
    payload: dict | None = None
    status: str = 'not_checked'

    @classmethod
    def load(cls, path: Path):
        if not path.exists():
            return cls()
        return cls(**read_json(path))

    def save(self, path: Path):
        write_json(path, asdict(self))

    def due(self, now: float) -> bool:
        return now >= self.retry_at

    def response(self, code: int, headers: dict, body: dict | None, now: float):
        headers = {k.lower(): v for k, v in headers.items()}
        if code == 304:
            if self.payload is None:
                self.etag = ''
                self.status = 'cache_missing'
                self.retry_at = now + 60
            else:
                self.status = 'cached'
                self.failures = 0
                self.retry_at = now + 3600
            return
        if code == 200:
            self.payload = body
            self.etag = headers.get('etag', '')
            self.status = 'available'
            self.failures = 0
            self.retry_at = now + 3600
            return
        if code == 404:
            self.payload, self.etag = None, ''
            self.status = 'no_release'
            self.retry_at = now + 3600
            return
        self.failures += 1
        delay = min(3600, 30 * 2 ** min(self.failures - 1, 7))
        deadline = now + delay
        limited = (code == 429 or (code == 403 and (
            headers.get('x-ratelimit-remaining') == '0' or 'retry-after' in headers
            or (isinstance(body,dict) and 'rate limit' in str(body.get('message','')).lower()))))
        if limited:
            retry = headers.get('retry-after', '')
            try:
                deadline = max(deadline, now + float(retry))
            except ValueError:
                try:
                    deadline = max(deadline, parsedate_to_datetime(retry).timestamp())
                except (ValueError, TypeError):
                    pass
            try:
                deadline = max(deadline, float(headers.get('x-ratelimit-reset', '0')) + 5)
            except ValueError:
                pass
            self.status = 'rate_limited'
        elif code in (401,403):
            self.status = 'access_denied'
            deadline = max(deadline,now + 3600)
        else:
            self.status = 'network_error'
        self.retry_at = deadline

    def retry_time(self):
        return datetime.fromtimestamp(self.retry_at, timezone.utc).isoformat()
