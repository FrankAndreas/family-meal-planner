"""Who is logged in, and the planner's people. They come from the family hub (spec 2026-10-30): login, name, role and
language are managed there; the planner keeps its own data per person and deletes it for people the hub removed."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from . import auth, config, hub, hub_people, models, schemas
from .database import get_db
from .errors import api_error

router = APIRouter(tags=["users"])


def user_out(user: models.User) -> schemas.UserOut:
    return schemas.UserOut(
        id=user.id,
        name=user.name,
        role=user.role,
        language=user.language or config.default_language(),
        language_chosen=user.language is not None,
    )


@router.get("/config")
def public_config():
    """What the pages need before anyone is logged in (e.g. "no access"): the language for browsers that speak
    neither German nor English."""
    return {"default_language": config.default_language()}


@router.get("/hub")
def hub_link(request: Request):
    """Where browsers log in (the family hub's address at home) and out: at home the hub's logout page, which ends the
    login for every app; from outside Cloudflare Access's logout."""
    outside = auth.TUNNEL_HEADER in request.headers
    logout = "/cdn-cgi/access/logout" if outside else f"{hub.public_url()}/logout"
    return {"login_url": hub.public_url(), "logout_url": logout}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(auth.get_current_user)):
    return user_out(user)


def _ask_the_hub(request: Request, db: Session) -> None:
    """The family list shows the hub's current state, not the one of up to a minute ago."""
    token, _ = auth.request_token(request)
    if token:
        try:
            hub_people.refresh(db, token, force=True)
        except hub.HubUnavailable:
            raise api_error(503, "hub_unavailable") from None


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(request: Request, _parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """The people the hub lists for the planner."""
    _ask_the_hub(request, db)
    active = db.query(models.User).filter(models.User.is_active.is_(True)).order_by(models.User.name_key)
    return [user_out(u) for u in active]


@router.get("/users/removed", response_model=list[schemas.UserOut])
def removed_users(
    request: Request, _parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)
):
    """People the hub no longer lists: hidden with their data until a parent deletes it."""
    _ask_the_hub(request, db)
    hidden = db.query(models.User).filter(models.User.is_active.is_(False)).order_by(models.User.name_key)
    return [user_out(u) for u in hidden]


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, _parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    """Deletes a removed person's stars, favourites and sender addresses; their recipes and inbox items stay."""
    user = db.get(models.User, user_id)
    if user is None:
        raise api_error(404, "user_not_found")
    # Only people the hub no longer lists: an active family member's data is never deleted by mistake
    if user.is_active:
        raise api_error(409, "still_in_hub")
    db.delete(user)
    db.commit()
