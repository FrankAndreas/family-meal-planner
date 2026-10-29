import logging
import re
import secrets

from sqlalchemy.orm import Session

from . import auth, config, models

logger = logging.getLogger(__name__)


def seed_admin(db: Session) -> str | None:
    """Create the parent "Admin" on an empty database; returns its PIN, or None if users exist."""
    if db.query(models.User).first() is not None:
        return None
    pin = config.env("INITIAL_ADMIN_PIN")
    if not re.fullmatch(r"\d{4}", pin):
        if pin:
            logger.warning("INITIAL_ADMIN_PIN must be 4 digits; using a random PIN instead")
        pin = f"{secrets.randbelow(10_000):04d}"
    db.add(
        models.User(
            name="Admin", name_key=auth.name_key("Admin"), pin_hash=auth.get_pin_hash(pin), role=models.UserRole.PARENT
        )
    )
    db.commit()
    return pin
