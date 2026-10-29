from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from .models import UserRole

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
