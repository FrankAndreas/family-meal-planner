"""Recipe mails. On arrival only the headers and the MIME structure are read (summarize); the content is decoded
only when a parent processes the mail (content)."""

import email
import email.policy
import email.utils
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


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
