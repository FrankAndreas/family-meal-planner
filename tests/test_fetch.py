import pytest

from app import fetch


@pytest.fixture
def net(monkeypatch):
    """Fake DNS and HTTP: names map to addresses, (ip, path) to (status, headers, body)."""
    dns = {
        "public.example": ["93.184.216.34"],
        "inside.example": ["10.1.1.1"],
        "nas.local": ["192.168.1.10"],
        # NAT64: an IPv6 name for the home network's 192.168.1.10
        "nat64.example": ["64:ff9b::c0a8:10a"],
    }
    pages: dict = {}
    opened = []
    # The deadline each opening got (fetch._deadlines, for test_every_fetch_has_a_deadline)
    deadlines: list = []

    monkeypatch.setattr(fetch, "_resolve", lambda host, port: dns.get(host, [host]))

    def _open(scheme, host, port, target, ip, timeout, deadline=None):
        opened.append((host, ip, target))
        deadlines.append(deadline)
        return pages.get((host, target), (404, {}, b""))

    monkeypatch.setattr(fetch, "_open", _open)
    monkeypatch.setattr(fetch, "_deadlines", deadlines, raising=False)
    return dns, pages, opened


HTML = {"content-type": "text/html; charset=utf-8"}


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "http://[fd00::1]/",
        # IPv6 forms of an IPv4 address inside: NAT64 (well-known and local prefix) and the old IPv4-compatible form
        "http://[64:ff9b::7f00:1]/",
        "http://[64:ff9b::c0a8:10a]/",
        "http://[64:ff9b:1::a00:5]/",
        "http://[::127.0.0.1]/",
        "http://nat64.example/",
        "http://inside.example/",
        "http://nas.local/",
        "http://public.example:8080/",
        "ftp://public.example/",
        "file:///etc/passwd",
    ],
)
def test_refused(net, url):
    _, _, opened = net
    with pytest.raises(fetch.FetchRefused):
        fetch.fetch(url)
    assert opened == []


def test_public_page(net):
    _, pages, _ = net
    pages[("public.example", "/r?x=1")] = (200, HTML, "<p>Rösti</p>".encode())
    page = fetch.fetch("https://public.example/r?x=1")
    assert page.text == "<p>Rösti</p>" and page.url == "https://public.example/r?x=1"


def test_redirect_into_home_network_refused(net):
    _, pages, _ = net
    pages[("public.example", "/r")] = (302, {"location": "http://127.0.0.1/admin"}, b"")
    with pytest.raises(fetch.FetchRefused):
        fetch.fetch("https://public.example/r")


def test_redirect_followed(net):
    _, pages, _ = net
    pages[("public.example", "/a")] = (301, {"location": "/b"}, b"")
    pages[("public.example", "/b")] = (200, HTML, b"ok")
    assert fetch.fetch("https://public.example/a").url == "https://public.example/b"


def test_too_many_redirects(net):
    _, pages, _ = net
    pages[("public.example", "/loop")] = (302, {"location": "/loop"}, b"")
    with pytest.raises(fetch.FetchFailed):
        fetch.fetch("https://public.example/loop")


def test_too_big(net, monkeypatch):
    _, pages, _ = net
    monkeypatch.setattr(fetch, "MAX_BYTES", 10)
    pages[("public.example", "/big")] = (200, HTML, b"x" * 11)
    with pytest.raises(fetch.FetchFailed):
        fetch.fetch("https://public.example/big")


def test_wrong_type(net):
    _, pages, _ = net
    pages[("public.example", "/f.zip")] = (200, {"content-type": "application/zip"}, b"PK")
    with pytest.raises(fetch.FetchFailed):
        fetch.fetch("https://public.example/f.zip")


def test_image_when_asked(net):
    _, pages, _ = net
    pages[("public.example", "/a.jpg")] = (200, {"content-type": "image/jpeg"}, b"\xff\xd8")
    assert fetch.fetch("https://public.example/a.jpg", accept=("image/",)).body == b"\xff\xd8"


def test_http_error(net):
    with pytest.raises(fetch.FetchFailed):
        fetch.fetch("https://public.example/missing")


@pytest.mark.parametrize("url", ["http://a..b/", "http://x.ch:abc/", "http://[::1/", "http://[x"])
def test_malformed_urls_refused(net, url):
    with pytest.raises(fetch.FetchRefused):
        fetch.fetch(url)


def test_allowlist_refuses_other_hosts_and_redirects(net):
    dns, pages, opened = net
    dns["www.swissmilk.ch"] = ["93.184.216.40"]
    dns["evil.example"] = ["93.184.216.41"]
    allowed = frozenset({"www.swissmilk.ch"})
    pages[("www.swissmilk.ch", "/a/")] = (302, {"location": "https://evil.example/x"}, b"")
    with pytest.raises(fetch.FetchRefused):
        fetch.fetch("https://www.swissmilk.ch/a/", allowed_hosts=allowed)
    assert [o[0] for o in opened] == ["www.swissmilk.ch"]
    with pytest.raises(fetch.FetchRefused):
        fetch.fetch("http://www.swissmilk.ch/a/", allowed_hosts=allowed)
    with pytest.raises(fetch.FetchRefused):
        fetch.fetch("https://evil.example/x", allowed_hosts=allowed)
    # Without an allowlist the redirect is followed as before
    pages[("evil.example", "/x")] = (200, HTML, b"<html></html>")
    assert fetch.fetch("https://www.swissmilk.ch/a/").url == "https://evil.example/x"


def test_deadline_ends_a_slow_trickle():
    """A server that sends one byte at a time can't hold a fetch past its deadline."""
    import socket
    import threading
    import time

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def drip():
        conn, _ = server.accept()
        conn.recv(1024)
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 100000\r\n\r\n")
        try:
            for _ in range(50):
                conn.sendall(b"x")
                time.sleep(0.2)
        except OSError:
            pass
        conn.close()

    threading.Thread(target=drip, daemon=True).start()
    started = time.monotonic()
    with pytest.raises(fetch.FetchFailed):
        fetch._open("http", "127.0.0.1", server.getsockname()[1], "/", "127.0.0.1", 10, deadline=started + 0.6)
    assert time.monotonic() - started < 1.5
    server.close()


def test_public_ipv4_behind_nat64_is_allowed(net):
    dns, pages, opened = net
    dns["v6.example"] = ["64:ff9b::808:808"]
    pages[("v6.example", "/")] = (200, HTML, b"<html></html>")
    assert fetch.fetch("https://v6.example/").url == "https://v6.example/"


def test_every_fetch_has_a_deadline(net):
    """Without a deadline from the caller a slow server could hold the request or the import for hours: the whole
    fetch ends after TOTAL_SECONDS."""
    import time

    _, pages, _ = net
    pages[("public.example", "/")] = (200, HTML, b"<html></html>")
    before = time.monotonic()
    fetch.fetch("https://public.example/")
    (deadline,) = fetch._deadlines
    assert deadline is not None and before + fetch.TOTAL_SECONDS - 1 <= deadline <= time.monotonic() + fetch.TOTAL_SECONDS


def test_deadline_passed_opens_nothing(net):
    import time

    _, pages, opened = net
    pages[("public.example", "/")] = (200, HTML, b"<html></html>")
    with pytest.raises(fetch.FetchFailed):
        fetch.fetch("https://public.example/", deadline=time.monotonic() - 1)
    assert opened == []


def _trickle_server(prefix: bytes, slow: bytes):
    """A local server that sends `prefix` at once, then `slow` one byte every 0.3 s."""
    import socket
    import threading
    import time

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def serve():
        conn, _ = server.accept()
        conn.recv(1024)
        try:
            conn.sendall(prefix)
            for byte in slow:
                conn.sendall(bytes([byte]))
                time.sleep(0.3)
        except OSError:
            pass
        conn.close()
        server.close()

    threading.Thread(target=serve, daemon=True).start()
    return server.getsockname()[1]


@pytest.mark.parametrize(
    "prefix, slow",
    [
        # Headers trickling in
        (b"HTTP/1.1 200 OK\r\n", b"X-Slow: " + b"a" * 100 + b"\r\n\r\n"),
        # A body without length on a closing connection
        (b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n", b"x" * 100),
    ],
)
def test_deadline_is_hard_in_every_phase(prefix, slow):
    import time

    port = _trickle_server(prefix, slow)
    started = time.monotonic()
    with pytest.raises(fetch.FetchFailed):
        fetch._open("http", "127.0.0.1", port, "/", "127.0.0.1", 10, deadline=started + 1.0)
    assert time.monotonic() - started < 2.0
