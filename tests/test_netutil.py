import http.client
import io
import json
import urllib.error

import pytest

import netutil


class FakeResp(io.BytesIO):
    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = headers or {}
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_user_agent_sent(monkeypatch):
    seen = {}

    def fake(req, timeout=None):
        seen["ua"] = req.get_header("User-agent")
        return FakeResp(b"{}")

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    netutil.get_json("https://example.com/x")
    assert seen["ua"].startswith("ppt-craft/")
    assert seen["ua"] == netutil.USER_AGENT


def test_429_raises_rate_limited(monkeypatch):
    def fake(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, None)

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    with pytest.raises(netutil.RateLimited):
        netutil.get_json("https://example.com/x")


def test_quota_header_zero_raises_rate_limited(monkeypatch):
    def fake(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {"X-RateLimit-Remaining": "0"}, None)

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    with pytest.raises(netutil.RateLimited):
        netutil.fetch("https://example.com/x")


def test_http_error_is_net_error_with_url_and_status(monkeypatch):
    def fake(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "Boom", {}, None)

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    with pytest.raises(netutil.NetError, match=r"https://example.com/x -> HTTP 500"):
        netutil.fetch("https://example.com/x")


def test_url_error_and_timeout_are_net_error(monkeypatch):
    for exc in (urllib.error.URLError("no route"), TimeoutError("slow")):
        def fake(req, timeout=None, exc=exc):
            raise exc

        monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
        with pytest.raises(netutil.NetError):
            netutil.fetch("https://example.com/x")


def test_cache_hit_and_expiry(monkeypatch, tmp_path):
    calls = []

    def fake(req, timeout=None):
        calls.append(1)
        return FakeResp(json.dumps({"n": len(calls)}).encode())

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    a = netutil.get_json("https://example.com/q?key=SECRET", cache_dir=tmp_path)
    b = netutil.get_json("https://example.com/q?key=SECRET", cache_dir=tmp_path)
    assert a == b == {"n": 1} and len(calls) == 1
    stored = next(tmp_path.glob("*.json")).read_text(encoding="utf-8")
    assert "SECRET" not in stored
    netutil.get_json("https://example.com/q?key=SECRET", cache_dir=tmp_path, ttl=0)
    assert len(calls) == 2


def test_cache_key_ignores_authorization_but_not_other_headers(monkeypatch, tmp_path):
    calls = []

    def fake(req, timeout=None):
        calls.append(1)
        return FakeResp(b"{}")

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    netutil.get_json("https://example.com/q", headers={"Authorization": "k1"}, cache_dir=tmp_path)
    netutil.get_json("https://example.com/q", headers={"Authorization": "k2"}, cache_dir=tmp_path)
    assert len(calls) == 1
    netutil.get_json("https://example.com/q", headers={"Accept": "x"}, cache_dir=tmp_path)
    assert len(calls) == 2
    assert all("k1" not in p.read_text(encoding="utf-8") for p in tmp_path.glob("*.json"))


def test_no_cache_dir_means_no_cache(monkeypatch):
    calls = []

    def fake(req, timeout=None):
        calls.append(1)
        return FakeResp(b"{}")

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    netutil.get_json("https://example.com/q")
    netutil.get_json("https://example.com/q")
    assert len(calls) == 2


def test_invalid_json_is_net_error(monkeypatch):
    monkeypatch.setattr(netutil.urllib.request, "urlopen", lambda req, timeout=None: FakeResp(b"<html>"))
    with pytest.raises(netutil.NetError):
        netutil.get_json("https://example.com/x")


def test_max_bytes(monkeypatch):
    monkeypatch.setattr(netutil.urllib.request, "urlopen", lambda req, timeout=None: FakeResp(b"x" * 100))
    with pytest.raises(netutil.NetError):
        netutil.get_bytes("https://example.com/big", max_bytes=10)
    assert netutil.get_bytes("https://example.com/big", max_bytes=100) == b"x" * 100


def test_fetch_post_sends_data_and_method(monkeypatch):
    seen = {}

    def fake(req, timeout=None):
        seen.update(method=req.get_method(), data=req.data, ct=req.get_header("Content-type"), timeout=timeout)
        return FakeResp(b"ok")

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    assert netutil.fetch("https://example.com/p", data=b"abc", headers={"Content-Type": "text/plain"}) == b"ok"
    assert seen == {"method": "POST", "data": b"abc", "ct": "text/plain", "timeout": 30}


def test_get_is_default_method(monkeypatch):
    seen = {}

    def fake(req, timeout=None):
        seen["method"] = req.get_method()
        return FakeResp(b"")

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    netutil.fetch("https://example.com/g")
    assert seen["method"] == "GET"


def test_post_json_roundtrip_and_no_cache(monkeypatch, tmp_path):
    seen = {}

    def fake(req, timeout=None):
        seen.update(method=req.get_method(), body=json.loads(req.data), ct=req.get_header("Content-type"),
                    auth=req.get_header("Authorization"), timeout=timeout)
        return FakeResp(b'{"image": "abc"}')

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    out = netutil.post_json("https://example.com/gen", {"prompt": "a cat"}, headers={"Authorization": "Bearer t"})
    assert out == {"image": "abc"}
    assert seen == {"method": "POST", "body": {"prompt": "a cat"}, "ct": "application/json",
                    "auth": "Bearer t", "timeout": 120}


def test_incomplete_read_is_net_error_without_secret(monkeypatch):
    def fake(req, timeout=None):
        raise http.client.IncompleteRead(b"abc", 5)

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    with pytest.raises(netutil.NetError) as e:
        netutil.fetch("https://example.com/x?key=SECRET&q=1")
    assert "SECRET" not in str(e.value) and "example.com/x" in str(e.value)


def test_http_exception_during_read_is_net_error(monkeypatch):
    class Broken(FakeResp):
        def read(self, n=-1):
            raise http.client.IncompleteRead(b"", 10)

    monkeypatch.setattr(netutil.urllib.request, "urlopen", lambda req, timeout=None: Broken(b"x"))
    for call in (lambda: netutil.get_json("https://example.com/x"), lambda: netutil.get_bytes("https://example.com/x")):
        with pytest.raises(netutil.NetError):
            call()


def test_bad_url_value_error_is_net_error(monkeypatch):
    def fake(req, timeout=None):
        raise ValueError("bad url")

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    with pytest.raises(netutil.NetError):
        netutil.fetch("https://[bad/x?key=SECRET")  # urlsplit itself raises ValueError for this one


def test_secret_not_in_error_messages(monkeypatch):
    url = "https://example.com/x?key=SECRET&q=1"
    for code, exc in ((429, netutil.RateLimited), (500, netutil.NetError)):
        def fake(req, timeout=None, code=code):
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, None)

        monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
        with pytest.raises(exc) as e:
            netutil.fetch(url)
        assert "SECRET" not in str(e.value)
    monkeypatch.setattr(netutil.urllib.request, "urlopen", lambda req, timeout=None: FakeResp(b"x" * 100))
    with pytest.raises(netutil.NetError) as e:
        netutil.get_bytes(url, max_bytes=10)
    assert "SECRET" not in str(e.value)


def test_rate_limited_message_includes_retry_after(monkeypatch):
    def fake(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 429, "x", {"Retry-After": "120"}, None)

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    with pytest.raises(netutil.RateLimited, match=r"example.com: rate limited \(Retry-After: 120\)"):
        netutil.fetch("https://example.com/x")


def test_https_only(monkeypatch):
    called = []
    monkeypatch.setattr(netutil.urllib.request, "urlopen", lambda req, timeout=None: called.append(1))
    for url in ("http://example.com/x", "file:///etc/passwd", "ftp://example.com/x"):
        with pytest.raises(netutil.NetError, match="https"):
            netutil.fetch(url)
    assert not called


def test_cache_write_failure_is_ignored(monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")  # cache_dir below a regular file: mkdir raises OSError
    monkeypatch.setattr(netutil.urllib.request, "urlopen", lambda req, timeout=None: FakeResp(b'{"a": 1}'))
    assert netutil.get_json("https://example.com/x", cache_dir=blocker / "cache") == {"a": 1}


def test_corrupt_cache_file_is_a_miss(monkeypatch, tmp_path):
    calls = []

    def fake(req, timeout=None):
        calls.append(1)
        return FakeResp(b'{"a": 1}')

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    netutil.get_json("https://example.com/x", cache_dir=tmp_path)
    for bad in ("{not json", "[]", '{"t": "x", "data": 1}', ""):
        next(tmp_path.glob("*.json")).write_text(bad, encoding="utf-8")
        assert netutil.get_json("https://example.com/x", cache_dir=tmp_path) == {"a": 1}
    assert len(calls) == 5


def test_value_error_reason_is_only_the_type_name(monkeypatch):
    def fake(req, timeout=None):
        raise http.client.InvalidURL("URL can't contain control characters. '/x?key=SECRET' (found at least ' ')")

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    with pytest.raises(netutil.NetError) as e:
        netutil.fetch("https://example.com/x?key=SECRET")
    assert "SECRET" not in str(e.value) and "InvalidURL" in str(e.value)


def test_authorization_is_sent_unredirected(monkeypatch):
    seen = {}

    def fake(req, timeout=None):
        seen.update(headers=dict(req.headers), unredirected=dict(req.unredirected_hdrs), value=req.get_header("Authorization"))
        return FakeResp(b"{}")

    monkeypatch.setattr(netutil.urllib.request, "urlopen", fake)
    netutil.fetch("https://example.com/x", headers={"authorization": "Bearer T", "Accept": "x"})
    assert seen["value"] == "Bearer T" and seen["unredirected"] == {"Authorization": "Bearer T"}
    assert "Authorization" not in seen["headers"] and "authorization" not in seen["headers"]
    assert seen["headers"]["Accept"] == "x"


def _redirect(req, newurl):
    handler = netutil._HttpsOnlyRedirect()
    return handler.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, newurl)


def test_redirected_request_does_not_carry_authorization():
    req = netutil.urllib.request.Request("https://api.example.com/x", headers={"User-Agent": "ua"})
    req.add_unredirected_header("Authorization", "Bearer T")
    new = _redirect(req, "https://cdn.other.net/y")
    assert new.full_url == "https://cdn.other.net/y"
    assert new.get_header("Authorization") is None and "Authorization" not in new.unredirected_hdrs


def test_https_to_http_redirect_is_refused():
    req = netutil.urllib.request.Request("https://api.example.com/x")
    with pytest.raises(netutil.NetError, match="non-https"):
        _redirect(req, "http://evil.example.net/y?key=SECRET")
    with pytest.raises(netutil.NetError):
        _redirect(req, "ftp://evil.example.net/y")


def test_https_redirect_handler_is_installed_for_urlopen():
    handlers = netutil.urllib.request._opener.handlers
    assert any(isinstance(h, netutil._HttpsOnlyRedirect) for h in handlers)
