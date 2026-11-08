"""Fetching a recipe page named in a mail or pasted by someone: only public web servers, never the home network.

The address is checked after resolving the name and the connection goes to exactly that address (no second lookup
an attacker could answer differently), for every redirect."""

import http.client
import ipaddress
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 5
CHUNK = 64 * 1024
TIMEOUT = 10
# The whole fetch (redirects and reading included) ends by then at the latest, also when the caller sets no deadline:
# a server trickling a byte every few seconds can't hold a request or an import
TOTAL_SECONDS = 30
# NAT64 (RFC 6052): IPv6 addresses standing for an IPv4 address, which a NAT64 gateway at home would reach
NAT64 = ipaddress.ip_network("64:ff9b::/96")
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


def _public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """A public address, also when it is an IPv6 form of an IPv4 address (NAT64, or the old IPv4-compatible
    ::a.b.c.d): then the IPv4 address it stands for must be public too. IPv4-mapped (::ffff:a.b.c.d) is checked by
    is_global itself."""
    if not ip.is_global:
        return False
    if ip.version == 6 and (ip in NAT64 or int(ip) >> 32 == 0):
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF).is_global
    return True


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
        # Kept, so a deadline can cut the connection in any phase (handshake, headers, body)
        self.raw_sock = sock
        self.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, ip, **kwargs):
        super().__init__(host, **kwargs)
        self._ip = ip

    def connect(self):
        self.sock = self.raw_sock = socket.create_connection((self._ip, self.port), self.timeout)


def _open(
    scheme: str, host: str, port: int, target: str, ip: str, timeout: float, deadline: float | None = None
) -> tuple[int, dict, bytes]:
    kind = _PinnedHTTPS if scheme == "https" else _PinnedHTTP
    connection = kind(host, ip, port=port, timeout=timeout)
    watchdog = None
    if deadline is not None:
        # At the deadline the connection is cut, whatever it's waiting for: a server trickling its handshake,
        # headers or body can't hold the fetch
        watchdog = threading.Timer(max(0.0, deadline - time.monotonic()), _cut, (connection,))
        watchdog.daemon = True
        watchdog.start()
    try:
        connection.request("GET", target, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"})
        response = connection.getresponse()
        headers = {k.lower(): v for k, v in response.getheaders()}
        body = bytearray()
        while len(body) <= MAX_BYTES:
            piece = response.read1(CHUNK)
            if not piece:
                break
            body += piece
        if deadline is not None and time.monotonic() >= deadline:
            raise FetchFailed("deadline")
        return response.status, headers, bytes(body)
    except (OSError, http.client.HTTPException) as error:
        raise FetchFailed("deadline" if deadline is not None and time.monotonic() >= deadline else "connection") from error
    finally:
        if watchdog is not None:
            watchdog.cancel()
        connection.close()


def _cut(connection) -> None:
    sock = getattr(connection, "raw_sock", None)
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def _checked(url: str) -> tuple[str, str, int, str, str]:
    # A malformed address (bad port, broken brackets, empty labels) is refused like an unsafe one
    try:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        host = parts.hostname
        port = parts.port or (443 if scheme == "https" else 80)
        if scheme not in ("http", "https") or not host or port not in (80, 443):
            raise FetchRefused(url)
        addresses = _resolve(host, port)
    except (ValueError, UnicodeError) as error:
        raise FetchRefused(url) from error
    if not addresses:
        raise FetchFailed("dns")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%")[0])
        except ValueError:
            raise FetchRefused(url)
        if not _public(ip):
            raise FetchRefused(url)
    target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return scheme, host, port, target, addresses[0]


def _allowed(url: str, allowed_hosts: frozenset[str]) -> None:
    """With an allowlist: HTTPS to one of these hosts only, for the first address and every redirect."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
    except ValueError as error:
        raise FetchRefused(url) from error
    if parts.scheme.lower() != "https" or host not in allowed_hosts:
        raise FetchRefused(url)


def fetch(
    url: str,
    accept: tuple[str, ...] = PAGE_TYPES,
    *,
    allowed_hosts: frozenset[str] | None = None,
    deadline: float | None = None,
) -> Page:
    """`deadline` (time.monotonic()): the whole fetch, redirects and reading included, ends by then; at the latest
    TOTAL_SECONDS from now."""
    latest = time.monotonic() + TOTAL_SECONDS
    deadline = latest if deadline is None else min(deadline, latest)
    for _ in range(MAX_REDIRECTS + 1):
        if allowed_hosts is not None:
            _allowed(url, allowed_hosts)
        if deadline <= time.monotonic():
            raise FetchFailed("deadline")
        scheme, host, port, target, ip = _checked(url)
        timeout = max(0.1, min(TIMEOUT, deadline - time.monotonic()))
        status, headers, body = _open(scheme, host, port, target, ip, timeout, deadline=deadline)
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
