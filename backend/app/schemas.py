import datetime as dt
import re
from urllib.parse import urlsplit
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from .categories import Category, clean
from .models import InboxKind, InboxStatus, UserRole
from .units import UNITS

Pin = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Language = Literal["de", "en"]
# How a recipe came in: typed, or from the inbox (InboxKind)
SourceKind = Literal["manual", "url", "mail", "scan", "text"]








class UserOut(BaseModel):
    id: int
    name: str
    role: UserRole
    # The language the person sees: their own choice, or the default language
    language: Language
    language_chosen: bool
    # Confirmed in the family hub and shared with the planner: recipe mails come from it
    email: str | None












class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    family_size: int
    week_start: int
    staples: list[str]


class SettingsPatch(BaseModel):
    family_size: Annotated[int, Field(ge=1, le=20)] | None = None
    # Python weekday: 0 = Monday ... 6 = Sunday
    week_start: Annotated[int, Field(ge=0, le=6)] | None = None
    # What's always at home; blanks trimmed, the same word twice (any case) kept once
    staples: Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=50)] | None = None

    @field_validator("staples")
    @classmethod
    def clean_staples(cls, staples: list[str] | None) -> list[str] | None:
        if staples is None:
            return None
        result: list[str] = []
        for word in (s.strip() for s in staples):
            if not word:
                raise ValueError("staple_empty")
            if word.casefold() not in {r.casefold() for r in result}:
                result.append(word)
        return result


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class IngredientIn(BaseModel):
    group: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    amount: Annotated[float, Field(gt=0)] | None = None
    unit: str | None = None
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""

    @field_validator("unit")
    @classmethod
    def known_unit(cls, unit: str | None) -> str | None:
        if unit is not None and unit not in UNITS:
            raise ValueError("unknown_unit")
        return unit

    @field_validator("group")
    @classmethod
    def blank_group_is_none(cls, group: str | None) -> str | None:
        return group or None


# A yield "unit" that just says people: such a recipe scales by its own servings, not by the family size
# "scheme:rest" without spaces: an address, not a text
OTHER_ADDRESS = re.compile(r"[a-z][a-z0-9+.-]*:\S*$", re.IGNORECASE)
PEOPLE_WORDS = {"person", "personen", "pers", "portion", "portionen", "people", "persons", "serving", "servings"}


class RecipeIn(BaseModel):
    title: Title
    servings: Annotated[float, Field(gt=0, le=100)]
    servings_unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None
    prep_minutes: Annotated[int, Field(ge=0, le=1440)] | None = None
    cook_minutes: Annotated[int, Field(ge=0, le=1440)] | None = None
    ingredients: Annotated[list[IngredientIn], Field(max_length=200)] = []
    steps: Annotated[list[str], Field(max_length=100)] = []
    tags: Annotated[list[Annotated[str, StringConstraints(max_length=40)]], Field(max_length=20)] = []
    categories: Annotated[list[Category], Field(max_length=20)] = []
    notes: Annotated[str, StringConstraints(max_length=10_000)] = ""
    source_kind: SourceKind = "manual"
    source_url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    language: Language | None = None
    # Saving a draft from the inbox: the item it came from (its photo is taken over, the item is done)
    inbox_item_id: int | None = None

    @field_validator("servings_unit")
    @classmethod
    def people_unit_is_none(cls, unit: str | None) -> str | None:
        if not unit or unit.casefold().rstrip(".") in PEOPLE_WORDS:
            return None
        return unit

    @field_validator("source_url")
    @classmethod
    def web_link(cls, url: str | None) -> str | None:
        # A web link (shown as a link) or a text like "Betty Bossi, S. 42" (shown as text);
        # never an address like javascript: or file: from an import
        if url and OTHER_ADDRESS.match(url) and not url.lower().startswith(("http://", "https://")):
            raise ValueError("not_a_web_link")
        return url or None

    @field_validator("categories")
    @classmethod
    def categories_in_order(cls, categories: list[str]) -> list[str]:
        return clean(categories)

    @field_validator("steps")
    @classmethod
    def no_blank_steps(cls, steps: list[str]) -> list[str]:
        return [step.strip() for step in steps if step.strip()]


class IngredientOut(BaseModel):
    id: int
    group: str | None
    amount: float | None
    unit: str | None
    name: str
    note: str
    # The amount for `people` (rounded), the same as amount at the recipe's own yield
    scaled_amount: float | None


class RatingOut(BaseModel):
    user_id: int
    name: str
    stars: int


class RecipeSummary(BaseModel):
    id: int
    title: str
    photo_url: str | None
    tags: list[str]
    categories: list[Category]
    servings: float
    servings_unit: str | None
    total_minutes: int | None
    rating_avg: float | None
    rating_count: int
    my_rating: int | None
    my_favorite: bool
    favorite_count: int
    last_eaten: dt.date | None
    times_eaten: int


class UseUpOut(RecipeSummary):
    """A recipe for what's at home: which typed ingredients it uses, and what's missing (neither typed nor a basic)."""

    used: list[str]
    missing: list[str]


class SwissmilkResult(BaseModel):
    """A Swissmilk recipe for what's at home: its photo comes through the app, never from Swissmilk directly."""

    title: str
    url: str
    photo: str | None
    used: list[str]
    missing: list[str]
    # The family's recipe from this Swissmilk recipe, or it's waiting in the inbox
    recipe_id: int | None
    waiting: bool


class SourceMail(BaseModel):
    """The mail or pasted link a recipe was saved from: who sent it, and when."""

    id: int
    kind: InboxKind
    user_name: str | None
    received_at: dt.datetime


class OriginalIngredient(BaseModel):
    name: str = ""
    note: str = ""


class Original(BaseModel):
    """A recipe's text before an AI translation (amounts and units never change in one)."""

    title: str = ""
    ingredients: list[OriginalIngredient] = []
    steps: list[str] = []
    notes: str = ""
    tags: list[str] = []
    language: Language | None = None


class RecipeOut(RecipeSummary):
    prep_minutes: int | None
    cook_minutes: int | None
    steps: list[str]
    notes: str
    source_kind: SourceKind
    source_url: str | None
    language: Language | None
    created_by_name: str | None
    deleted: bool
    ingredients: list[IngredientOut]
    ratings: list[RatingOut]
    people: float | None
    factor: float
    inbox_item_id: int | None
    source_mail: SourceMail | None
    original: Original | None
    translate_into: Language | None


class TagCount(BaseModel):
    name: str
    count: int


class RatingIn(BaseModel):
    stars: Annotated[int, Field(ge=1, le=5)] | None


class FavoriteIn(BaseModel):
    favorite: bool


Slot = Literal["breakfast", "snack", "lunch", "dinner"]
People = Annotated[float, Field(ge=0.5, le=100)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class EntryIn(BaseModel):
    date: dt.date
    slot: Slot
    recipe_id: int | None = None
    note: Note | None = None
    people: People | None = None

    @model_validator(mode="after")
    def recipe_or_note(self):
        if self.note == "":
            self.note = None
        if (self.recipe_id is None) == (self.note is None):
            raise ValueError("recipe_or_note")
        return self


class EntryPatch(BaseModel):
    date: dt.date | None = None
    slot: Slot | None = None
    position: Annotated[int, Field(ge=0)] | None = None
    people: People | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    eaten: bool | None = None


class EntryOut(BaseModel):
    id: int
    date: dt.date
    slot: Slot
    position: int
    recipe: RecipeSummary | None
    recipe_deleted: bool
    note: str | None
    people: float | None
    eaten: bool


class PlannedOut(BaseModel):
    date: dt.date
    slot: Slot


class WeekOut(BaseModel):
    start: dt.date
    end: dt.date
    days: list[dt.date]
    today: dt.date
    entries: list[EntryOut]
    closed: bool
    # The week before is over, not closed, and had recipes planned: the planner offers to close it first
    previous_needs_closing: bool
    planned_slots: int
    total_slots: int


class CloseIn(BaseModel):
    start: dt.date


class Attachment(BaseModel):
    """A part of a mail, from its MIME structure (not decoded)."""

    index: int
    name: str
    type: str
    size: int


class InboxItemOut(BaseModel):
    id: int
    kind: InboxKind
    status: InboxStatus
    user_name: str | None
    from_addr: str
    subject: str
    url: str | None
    received_at: dt.datetime
    attachments: list[Attachment]
    error: str | None
    recipe_id: int | None


def web_link(url: str) -> str:
    try:
        parts = urlsplit(url)
        ok = parts.scheme.lower() in ("http", "https") and bool(parts.hostname) and parts.port in (None, 80, 443)
    except ValueError:
        ok = False
    if not ok:
        raise ValueError("not_a_web_link")
    return url


class UrlIn(BaseModel):
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @field_validator("url")
    @classmethod
    def web_link(cls, url: str) -> str:
        return web_link(url)


class TextIn(BaseModel):
    """A recipe's text pasted in (a Facebook post's caption), with where it came from."""

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)]
    # Only kept as the recipe's source, never fetched
    url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None

    @field_validator("url")
    @classmethod
    def optional_link(cls, url: str | None) -> str | None:
        return web_link(url) if url else None


class InboxItemDetail(InboxItemOut):
    draft: dict | None
    ai_raw: str | None
    # A pasted text, as it was pasted
    text: str | None


class CategorizeIn(BaseModel):
    # One recipe (asked from its page), or the next batch of recipes without categories
    recipe_id: int | None = None


class CategorizeLeft(BaseModel):
    remaining: int


class CategorizeOut(CategorizeLeft):
    categorized: int


# Shopping list and Bring! (spec 2026-11-06)


class BringOut(BaseModel):
    email: str | None
    list_uuid: str | None
    list_name: str | None


class BringLoginIn(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class BringListOut(BaseModel):
    uuid: str
    name: str


class BringListsOut(BaseModel):
    lists: list[BringListOut]


class BringListIn(BaseModel):
    uuid: Annotated[str, StringConstraints(min_length=1, max_length=64)]


class ShoppingStartIn(BaseModel):
    week_start: dt.date
    replace: bool = False


class ShoppingTickIn(BaseModel):
    ticked: bool


class ShoppingChoiceIn(BaseModel):
    key: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    buy: bool | None


class ShoppingExtraIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    amount: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] = ""


class ShoppingSendIn(BaseModel):
    version: Annotated[str, StringConstraints(max_length=100)]
    specs: dict[Annotated[str, StringConstraints(max_length=200)], Annotated[str, StringConstraints(max_length=200)]]


class ShoppingMealOut(BaseModel):
    entry_id: int
    date: dt.date
    slot: Slot
    title: str
    people: float | None
    ticked: bool


class ShoppingNoteOut(BaseModel):
    date: dt.date
    slot: Slot
    note: str


class ShoppingAmountOut(BaseModel):
    amount: float
    unit: str | None


class ShoppingLineOut(BaseModel):
    key: str
    name: str
    amounts: list[ShoppingAmountOut]
    extras: list[str]
    meals: list[str]
    staple: bool
    # Describing words of the recipes ("mehligkochende"), part of the amount text Bring! gets
    details: list[str]
    buy: bool


class ShoppingExtraOut(BaseModel):
    id: int
    name: str
    amount: str


class ShoppingOut(BaseModel):
    week_start: dt.date
    week_end: dt.date
    started_by: str | None
    changed_by: str | None
    changed_at: dt.datetime
    meals: list[ShoppingMealOut]
    notes: list[ShoppingNoteOut]
    lines: list[ShoppingLineOut]
    extras: list[ShoppingExtraOut]
    version: str


class ShoppingStateOut(BaseModel):
    list: ShoppingOut | None


class ShoppingSentOut(BaseModel):
    sent: int
    # The list changed while it was being sent: it stays, to check and send what's missing
    kept: bool


class AiStatusOut(BaseModel):
    enabled: bool
    calls_left_this_hour: int


class AiUsageRow(BaseModel):
    user_name: str
    calls: int


class AiUsageOut(BaseModel):
    """AI calls this month per person, and all calls ever."""

    month: list[AiUsageRow]
    total: int
