import enum

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
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
    # name.casefold(): names are unique regardless of case ("lena" is "Lena")
    name_key = Column(String(50), unique=True, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CHILD, nullable=False)
    # The person's language in the family hub (None: the default language, DEFAULT_LANGUAGE)
    language = Column(String(2))
    # The person in the family hub (spec 2026-10-30): login, name, role and language come from there. None: a row from
    # before the hub, linked by name at the first sync
    hub_id = Column(Integer, unique=True)
    # False: the hub no longer lists the person for the planner; hidden with their data until a parent deletes it
    is_active = Column(Boolean, default=True, nullable=False)
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
    # The text before an AI translation (title, ingredient names and notes, steps, notes, language), else None
    original = Column(JSON)

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


class PlanEntry(Base):
    """A recipe or a note in one slot of one day. Entries belong to a date, never to a week: changing the first day
    of the week only regroups them."""

    __tablename__ = "plan_entries"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    # breakfast, snack, lunch or dinner
    slot = Column(String(10), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    # Recipes are only ever soft-deleted, so the entry keeps pointing at one
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="RESTRICT"))
    note = Column(String(200))
    people = Column(Float)
    # False: marked "not eaten" (when closing the week); it then doesn't count as eaten
    eaten = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=utcnow, nullable=False)

    recipe = relationship("Recipe")


class WeekClosure(Base):
    """A week someone closed. The range is stored, so a later change of the first day doesn't move it."""

    __tablename__ = "week_closures"

    start = Column(Date, primary_key=True)
    end = Column(Date, nullable=False)
    closed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    closed_at = Column(DateTime, default=utcnow, nullable=False)


class UserEmail(Base):
    """An address a family member sends recipes from; mail from any other address is refused."""

    __tablename__ = "user_emails"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Lowercase
    address = Column(String(200), nullable=False, unique=True)

    user = relationship("User")


class InboxItem(Base):
    """A mail or a pasted link waiting to become a recipe. Nothing in it is read beyond the headers until a parent
    processes it."""

    __tablename__ = "inbox_items"

    id = Column(Integer, primary_key=True)
    # mail or url
    kind = Column(String(10), nullable=False)
    # waiting, processing, draft, failed, done
    status = Column(String(12), nullable=False, default="waiting")
    # Who sent the mail or pasted the link
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    from_addr = Column(String(200), nullable=False, default="")
    subject = Column(String(300), nullable=False, default="")
    url = Column(String(1000))
    message_id = Column(String(500), unique=True)
    received_at = Column(DateTime, default=utcnow, nullable=False)
    # [{index, name, type, size}] from the MIME structure, without decoding
    attachments = Column(JSON, nullable=False, default=list)
    size = Column(Integer, nullable=False, default=0)
    # An error code (errors.* in the frontend) of the last processing
    error = Column(String(100))
    # The recipe draft processing produced, for a person to check
    draft = Column(JSON)
    # The AI's answer as it came, kept as part of the original
    ai_raw = Column(Text)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="SET NULL"))
    processing_since = Column(DateTime)

    user = relationship("User")


class AiCall(Base):
    """One call to the AI service: the hourly limit counts these, and they are the usage log parents see."""

    __tablename__ = "ai_calls"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    at = Column(DateTime, default=utcnow, nullable=False, index=True)
    # import or translate
    purpose = Column(String(20), nullable=False)
    item_id = Column(Integer)
    recipe_id = Column(Integer)
    tokens = Column(Integer)

    user = relationship("User")
