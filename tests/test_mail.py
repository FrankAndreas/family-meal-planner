import email.message

from app import mail
from mails import build_mail, png


def test_summary_reads_headers_and_structure_only(monkeypatch):
    raw = build_mail(subject="Älplermagronen", images=[("a.png", png()), ("b.png", png())], message_id="<x@y>")

    def refuse(*args, **kwargs):
        if kwargs.get("decode") or (len(args) > 1 and args[1]):
            raise AssertionError("a part was decoded")
        return original(*args, **kwargs)

    original = email.message.Message.get_payload
    monkeypatch.setattr(email.message.Message, "get_payload", refuse)
    summary = mail.summarize(raw)
    assert summary.from_addr == "papa@example.ch"
    assert summary.subject == "Älplermagronen"
    assert summary.message_id == "<x@y>"
    assert [(a["index"], a["name"], a["type"]) for a in summary.attachments] == [
        (0, "a.png", "image/png"),
        (1, "b.png", "image/png"),
    ]
    assert all(a["size"] > 0 for a in summary.attachments)


def test_summary_without_message_id_uses_a_hash():
    assert mail.summarize(build_mail()).message_id.startswith("sha256:")


def test_summary_survives_garbage():
    summary = mail.summarize(b"\xff\xfe not a mail at all")
    assert summary.from_addr is None and summary.attachments == []
