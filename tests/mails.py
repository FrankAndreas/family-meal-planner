import io
from email.message import EmailMessage

from PIL import Image


def png(color=(200, 80, 40), size=(600, 400)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


def build_mail(
    from_addr="papa@example.ch",
    subject="Rezept",
    text="Schau mal",
    html=None,
    images=(),
    message_id=None,
    attachments=(),
) -> bytes:
    """A mail as a phone sends it when sharing: text, maybe HTML, and images attached."""
    message = EmailMessage()
    message["From"] = f"Papa <{from_addr}>"
    message["To"] = "rezepte@example.ch"
    message["Subject"] = subject
    message["Date"] = "Thu, 29 Oct 2026 20:15:00 +0100"
    if message_id:
        message["Message-ID"] = message_id
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    for name, data in images:
        message.add_attachment(data, maintype="image", subtype="png", filename=name)
    for name, data, kind in attachments:
        maintype, subtype = kind.split("/")
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return message.as_bytes()
