from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from .models import UserRole
from .units import UNITS

Pin = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class LoginIn(BaseModel):
    name: str
    pin: str


class TokenOut(BaseModel):
    access_token: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserOut(BaseModel):
    id: int
    name: str
    role: UserRole
    # The language the person sees: their own choice, or the default language
    language: Literal["de", "en"]
    language_chosen: bool


class MePatch(BaseModel):
    language: Literal["de", "en"] | None


class PinChange(BaseModel):
    current_pin: str
    new_pin: Pin


class PinReset(BaseModel):
    pin: Pin


class UserCreate(BaseModel):
    name: Name
    pin: Pin
    role: UserRole = UserRole.CHILD


class UserPatch(BaseModel):
    name: Name | None = None
    role: UserRole | None = None


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    family_size: int
    week_start: int


class SettingsPatch(BaseModel):
    family_size: Annotated[int, Field(ge=1, le=20)] | None = None
    # Python weekday: 0 = Monday ... 6 = Sunday
    week_start: Annotated[int, Field(ge=0, le=6)] | None = None


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


class RecipeIn(BaseModel):
    title: Title
    servings: Annotated[float, Field(gt=0, le=100)]
    servings_unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None
    prep_minutes: Annotated[int, Field(ge=0, le=1440)] | None = None
    cook_minutes: Annotated[int, Field(ge=0, le=1440)] | None = None
    ingredients: Annotated[list[IngredientIn], Field(max_length=200)] = []
    steps: Annotated[list[str], Field(max_length=100)] = []
    tags: Annotated[list[Annotated[str, StringConstraints(max_length=40)]], Field(max_length=20)] = []
    notes: Annotated[str, StringConstraints(max_length=10_000)] = ""
    source_kind: Literal["manual", "url", "mail"] = "manual"
    source_url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    language: Literal["de", "en"] | None = None

    @field_validator("servings_unit", "source_url")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        return value or None

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
    servings: float
    servings_unit: str | None
    total_minutes: int | None
    rating_avg: float | None
    rating_count: int
    my_rating: int | None
    my_favorite: bool
    favorite_count: int


class RecipeOut(RecipeSummary):
    prep_minutes: int | None
    cook_minutes: int | None
    steps: list[str]
    notes: str
    source_kind: str
    source_url: str | None
    language: str | None
    created_by_name: str | None
    deleted: bool
    ingredients: list[IngredientOut]
    ratings: list[RatingOut]
    people: float | None
    factor: float


class TagCount(BaseModel):
    name: str
    count: int


class RatingIn(BaseModel):
    stars: Annotated[int, Field(ge=1, le=5)] | None


class FavoriteIn(BaseModel):
    favorite: bool
