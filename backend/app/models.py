import enum

from sqlalchemy import Column, DateTime, Enum, Integer, String

from .database import Base
from .timeutil import utcnow


class UserRole(str, enum.Enum):
    PARENT = "PARENT"
    CHILD = "CHILD"


class User(Base):
    __tablename__ = "users"
    # Never reuse ids: login tokens name the user by id, so a deleted user's token must not match a new user
    __table_args__ = {"sqlite_autoincrement": True}

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    # name.casefold(): names are unique and logins match regardless of case ("lena" is "Lena")
    name_key = Column(String(50), unique=True, nullable=False)
    pin_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CHILD, nullable=False)
    # None: the default language (DEFAULT_LANGUAGE)
    language = Column(String(2))
    failed_logins = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime)
    # Locks in a row: each one doubles the next (see auth.lock_duration); a correct login or a new PIN resets it
    lockouts = Column(Integer, default=0, nullable=False)
    # Part of every login token; raising it ends all of the user's logins (new PIN)
    token_version = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Settings(Base):
    """The family's settings: a single row (id 1)."""

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    family_size = Column(Integer, default=4, nullable=False)
    # Python weekday: 0 = Monday ... 6 = Sunday; Saturday suits Friday planning and weekend shopping
    week_start = Column(Integer, default=5, nullable=False)
