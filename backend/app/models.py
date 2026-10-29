import enum

from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

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


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    # The yield: servings people, or (servings_unit set) e.g. 1 "Blech" or 20 "Stück"
    servings = Column(Float, nullable=False)
    servings_unit = Column(String(30))
    prep_minutes = Column(Integer)
    cook_minutes = Column(Integer)
    steps = Column(JSON, nullable=False, default=list)
    tags = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=False, default="")
    # manual, url or mail
    source_kind = Column(String(10), nullable=False, default="manual")
    source_url = Column(String(1000))
    # The language the recipe is written in (kept as imported), None if unknown
    language = Column(String(2))
    # File name in data/photos
    photo = Column(String(64))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    # Deleted recipes stay, so the history can still name them
    deleted_at = Column(DateTime)

    creator = relationship("User")
    ingredients = relationship(
        "RecipeIngredient",
        order_by="RecipeIngredient.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    # A heading the ingredient belongs under ("Für den Teig"), None for none
    group = Column(String(100))
    # None: not scaled ("Salz", "Pfeffer nach Belieben")
    amount = Column(Float)
    # One of units.UNITS, or None (counted things: "3 Eier")
    unit = Column(String(10))
    name = Column(String(200), nullable=False)
    note = Column(String(200), nullable=False, default="")


class Rating(Base):
    """One person's stars for a recipe."""

    __tablename__ = "ratings"

    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    stars = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User")


class Favorite(Base):
    __tablename__ = "favorites"

    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
