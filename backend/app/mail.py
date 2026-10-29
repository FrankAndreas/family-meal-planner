"""Recipe mails. On arrival only the headers and the MIME structure are read (summarize); the content is decoded
only when a parent processes the mail (content)."""

import email
import email.policy
import email.utils
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser


@dataclass
class MailSummary:
    from_addr: str | None
    subject: str
    sent_at: datetime | None
    message_id: str
    attachments: list[dict] = field(default_factory=list)


def clean(text: str, limit: int = 300) -> str:
    """Text a database can store: undecodable bytes become "?"."""
    return text.encode("utf-8", "replace").decode("utf-8", "replace").replace("�", "?").strip()[:limit]


def _header(message, name: str) -> str:
    try:
        return clean(str(message.get(name) or ""))
    except Exception:
        return ""


def _parse(raw: bytes):
    return email.message_from_bytes(raw, policy=email.policy.default)


def _attachment_parts(message) -> list:
    parts = []
    for part in message.walk():
        try:
            if part.is_multipart() or part.get_content_disposition() not in ("attachment", "inline"):
                continue
            if part.get_content_disposition() == "inline" and not part.get_filename():
                continue
        except Exception:
            continue
        parts.append(part)
    return parts


def summarize(raw: bytes) -> MailSummary:
    """Sender, subject, date and the attachments' names, types and sizes; no part is decoded."""
    try:
        message = _parse(raw)
    except Exception:
        return MailSummary(None, "?", None, "sha256:" + hashlib.sha256(raw).hexdigest())
    try:
        addresses = [a.lower() for _, a in email.utils.getaddresses([str(v) for v in message.get_all("From") or []])]
        senders = [a for a in addresses if "@" in a]
    except Exception:
        senders = []
    try:
        sent = email.utils.parsedate_to_datetime(_header(message, "Date"))
        sent_at = sent.astimezone(timezone.utc).replace(tzinfo=None) if sent.tzinfo else sent
    except Exception:
        sent_at = None
    attachments = []
    for index, part in enumerate(_attachment_parts(message)):
        try:
            name = clean(part.get_filename() or "", 200)
            kind = part.get_content_type()
            # The encoded payload's length: close enough, and nothing is decoded
            size = len(part.get_payload(decode=False) or "")
        except Exception:
            continue
        attachments.append({"index": index, "name": name, "type": kind, "size": size})
    message_id = _header(message, "Message-ID") or "sha256:" + hashlib.sha256(raw).hexdigest()
    return MailSummary(senders[0] if len(senders) == 1 else None, _header(message, "Subject") or "?", sent_at, message_id, attachments)


def attachment(raw: bytes, index: int) -> tuple[str, bytes] | None:
    """One attachment's type and bytes (decoded only when someone asks for it)."""
    parts = _attachment_parts(_parse(raw))
    if not 0 <= index < len(parts):
        return None
    part = parts[index]
    return part.get_content_type(), part.get_payload(decode=True) or b""


@dataclass
class MailContent:
    text: str
    links: list[str]
    # (attachment index, bytes) of the image attachments, in order
    images: list[tuple[int, bytes]]


class _Text(HTMLParser):
    """Visible text and link targets of an HTML mail part."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.links: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if href.lower().startswith(("http://", "https://")):
                self.links.append(href)
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_text(page: str) -> tuple[str, list[str]]:
    parser = _Text()
    try:
        parser.feed(page)
    except Exception:
        pass
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line), parser.links


LINK = re.compile(r"https?://[^\s<>\"')\]]+", re.I)


def content(raw: bytes) -> MailContent:
    """The whole mail, decoded: only when a parent processes it."""
    message = _parse(raw)
    plain = html = ""
    for part in message.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        try:
            if part.get_content_type() == "text/plain" and not plain:
                plain = part.get_content()
            elif part.get_content_type() == "text/html" and not html:
                html = part.get_content()
        except Exception:
            continue
    html_body, html_links = html_text(html) if html else ("", [])
    text = plain or html_body
    links: list[str] = []
    for link in LINK.findall(text) + html_links:
        link = link.rstrip(".,;:!?")
        if link not in links:
            links.append(link)
    images = []
    for index, part in enumerate(_attachment_parts(message)):
        try:
            if part.get_content_type().startswith("image/"):
                images.append((index, part.get_payload(decode=True) or b""))
        except Exception:
            continue
    return MailContent(text.strip(), links, images)
