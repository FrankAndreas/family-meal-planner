"""Fetching a recipe page named in a mail or pasted by someone: only public web servers, never the home network.

The address is checked after resolving the name and the connection goes to exactly that address (no second lookup
an attacker could answer differently), for every redirect."""

import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 5
TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Menüplaner; family use)"
PAGE_TYPES = ("text/html", "application/ld+json", "application/xhtml+xml")


class FetchRefused(Exception):
    """The address is not a public web server."""


class FetchFailed(Exception):
    """The page couldn't be loaded, or isn't what was asked for."""


@dataclass
class Page:
    url: str
    content_type: str
    body: bytes

    @property
    def text(self) -> str:
        charset = "utf-8"
        if "charset=" in self.content_type:
            charset = self.content_type.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
        try:
            return self.body.decode(charset, "replace")
        except LookupError:
            return self.body.decode("utf-8", "replace")


def _resolve(host: str, port: int) -> list[str]:
    try:
        return [info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]
    except OSError as error:
        raise FetchFailed("dns") from error


class _PinnedHTTPS(http.client.HTTPSConnection):
    """HTTPS to a checked address, with the name kept for the certificate (SNI)."""

    def __init__(self, host, ip, **kwargs):
        super().__init__(host, **kwargs)
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, ip, **kwargs):
        super().__init__(host, **kwargs)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


def _open(scheme: str, host: str, port: int, target: str, ip: str, timeout: float) -> tuple[int, dict, bytes]:
    kind = _PinnedHTTPS if scheme == "https" else _PinnedHTTP
    connection = kind(host, ip, port=port, timeout=timeout)
    try:
        connection.request("GET", target, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"})
        response = connection.getresponse()
        headers = {k.lower(): v for k, v in response.getheaders()}
        return response.status, headers, response.read(MAX_BYTES + 1)
    except (OSError, http.client.HTTPException) as error:
        raise FetchFailed("connection") from error
    finally:
        connection.close()


def _checked(url: str) -> tuple[str, str, int, str, str]:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not parts.hostname:
        raise FetchRefused(url)
    port = parts.port or (443 if scheme == "https" else 80)
    if port not in (80, 443):
        raise FetchRefused(url)
    addresses = _resolve(parts.hostname, port)
    if not addresses:
        raise FetchFailed("dns")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%")[0])
        except ValueError:
            raise FetchRefused(url)
        if not ip.is_global:
            raise FetchRefused(url)
    target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return scheme, parts.hostname, port, target, addresses[0]


def fetch(url: str, accept: tuple[str, ...] = PAGE_TYPES) -> Page:
    for _ in range(MAX_REDIRECTS + 1):
        scheme, host, port, target, ip = _checked(url)
        status, headers, body = _open(scheme, host, port, target, ip, TIMEOUT)
        if status in (301, 302, 303, 307, 308) and headers.get("location"):
            url = urljoin(url, headers["location"])
            continue
        if status != 200:
            raise FetchFailed(f"http {status}")
        if len(body) > MAX_BYTES:
            raise FetchFailed("too big")
        kind = headers.get("content-type", "").lower()
        if not any(kind.startswith(a) for a in accept):
            raise FetchFailed("type")
        return Page(url, kind, body)
    raise FetchFailed("redirects")
