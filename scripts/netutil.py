"""The single HTTP door: every network call in ppt-craft goes through fetch() (stdlib urllib only).
Adds a User-Agent, timeouts, a 24h on-disk JSON cache and rate-limit handling, so tests monkeypatch one place."""
import hashlib
import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class RateLimited(RuntimeError):
    """HTTP 429, or a quota header at 0."""


class NetError(RuntimeError):
    """Any other network/HTTP failure (the message includes the URL and status)."""


def _plugin_meta():
    version, home = "0.0.0", None
    try:
        meta = json.loads((Path(__file__).resolve().parents[1] / ".claude-plugin" / "plugin.json")
                          .read_text(encoding="utf-8"))
        version = meta.get("version", version)
        home = meta.get("homepage") or meta.get("repository")
        if isinstance(home, dict):
            home = home.get("url")
    except (OSError, ValueError):
        pass
    return version, home


_VERSION, _HOME = _plugin_meta()
USER_AGENT = f"ppt-craft/{_VERSION} (Claude Code plugin{f'; +{_HOME}' if _HOME else ''})"
CLIENT_AGENT = f"ppt-craft:{_VERSION}:{_HOME or 'unknown'}"  # AI Horde asks for this header


def _host(url):
    return urllib.parse.urlsplit(url).netloc or url


def _strip_secret(url):
    """URL without the `key=` query parameter (Pixabay) so secrets never reach the cache key or file."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return "<invalid url>"
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if k != "key"]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


class _HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to https URLs. (Unredirected headers such as Authorization are never copied to the new request.)"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlsplit(newurl)
        if parts.scheme != "https":
            raise NetError(f"{_host(req.full_url)}: redirect to a non-https URL refused ({parts.scheme or 'no scheme'}://{parts.netloc})")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


urllib.request.install_opener(urllib.request.build_opener(_HttpsOnlyRedirect))  # urlopen() below uses it


def fetch(url, *, headers=None, timeout=30, data=None, method=None, max_bytes=None):
    """The ONLY caller of urlopen. data: bytes for POST. max_bytes (internal, used by get_bytes): read in chunks, NetError if exceeded."""
    try:
        scheme = urllib.parse.urlsplit(url).scheme
    except ValueError:
        scheme = ""
    if scheme != "https":
        raise NetError(f"{_strip_secret(url)} -> only https URLs are allowed")
    headers = dict(headers or {})
    auth = next((headers.pop(k) for k in list(headers) if k.lower() == "authorization"), None)
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data is not None else "GET"),
                                 headers={"User-Agent": USER_AGENT, **headers})
    if auth is not None:  # unredirected: a redirect must never carry the token to another host
        req.add_unredirected_header("Authorization", auth)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if max_bytes is None:
                return resp.read()
            body = bytearray()
            while chunk := resp.read(65536):
                body += chunk
                if len(body) > max_bytes:
                    raise NetError(f"{_strip_secret(url)} -> response larger than {max_bytes} bytes")
            return bytes(body)
    except urllib.error.HTTPError as e:
        hdrs = e.headers or {}
        if e.code == 429 or str(hdrs.get("X-RateLimit-Remaining", "")) == "0":
            wait = hdrs.get("Retry-After")
            raise RateLimited(f"{_host(url)}: rate limited" + (f" (Retry-After: {wait})" if wait else "")) from e
        raise NetError(f"{_strip_secret(url)} -> HTTP {e.code}") from e
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as e:
        # URLError, timeouts, connection resets, IncompleteRead, bad URLs. The message uses the stripped URL (no `key=` secret).
        # ValueError and http.client.InvalidURL (an HTTPException) can embed the raw query, so only the type name is reported
        reason = type(e).__name__ if isinstance(e, (ValueError, http.client.HTTPException)) else getattr(e, "reason", e)
        raise NetError(f"{_strip_secret(url)} -> {reason}") from e


def _parse_json(body, url):
    try:
        return json.loads(body)
    except ValueError as e:
        raise NetError(f"{_strip_secret(url)} -> response is not JSON") from e


def get_json(url, *, headers=None, cache_dir=None, ttl=86400):
    clean = _strip_secret(url)
    path = None
    if cache_dir is not None:
        shown = sorted((k.lower(), v) for k, v in (headers or {}).items() if k.lower() != "authorization")
        key = hashlib.sha256((clean + repr(shown)).encode("utf-8")).hexdigest()
        path = Path(cache_dir) / f"{key}.json"
        try:
            hit = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - hit["t"] < ttl:
                return hit["data"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    data = _parse_json(fetch(url, headers=headers), url)
    if path is not None:
        try:  # the cache is best-effort: a read-only or full disk must not fail the request
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"t": time.time(), "url": clean, "data": data}, ensure_ascii=False),
                            encoding="utf-8")
        except OSError:
            pass
    return data


def get_bytes(url, *, headers=None, timeout=60, max_bytes=50_000_000):
    return fetch(url, headers=headers, timeout=timeout, max_bytes=max_bytes)


def post_json(url, payload, *, headers=None, timeout=120):
    """JSON body, JSON response, never cached."""
    h = {"Content-Type": "application/json", "Accept": "application/json", **(headers or {})}
    body = fetch(url, headers=h, timeout=timeout, data=json.dumps(payload).encode("utf-8"), method="POST")
    return _parse_json(body, url)
