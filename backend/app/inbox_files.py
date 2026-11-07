"""Where an inbox item's mail is kept (also a scan's pictures and a pasted text, as a mail): one file per item."""

from pathlib import Path

from . import config, models


def inbox_dir() -> Path:
    folder = config.data_dir() / "inbox"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def raw_path(item: models.InboxItem) -> Path:
    return inbox_dir() / f"{item.id}.eml"
