import pytest

from app import fetch


@pytest.fixture
def net(monkeypatch):
    """Fake DNS and HTTP: names map to addresses, (ip, path) to (status, headers, body)."""
    dns = {"public.example": ["93.184.216.34"], "inside.example": ["10.1.1.1"], "nas.local": ["192.168.1.10"]}
    pages: dict = {}
    opened = []

    monkeypatch.setattr(fetch, "_resolve", lambda host, port: dns.get(host, [host]))

    def _open(scheme, host, port, target, ip, timeout):
        opened.append((host, ip, target))
        return pages.get((host, target), (404, {}, b""))

    monkeypatch.setattr(fetch, "_open", _open)
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
