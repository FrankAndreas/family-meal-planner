from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from . import auth, config, models, schemas
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


def _get_user(db: Session, user_id: int) -> models.User:
    user = db.get(models.User, user_id)
    if user is None:
        raise api_error(404, "user_not_found")
    return user


def _parent_count(db: Session) -> int:
    return db.query(models.User).filter(models.User.role == models.UserRole.PARENT).count()


def _check_name_free(db: Session, name: str, except_id: int | None = None) -> None:
    query = db.query(models.User).filter(models.User.name_key == auth.name_key(name))
    if except_id is not None:
        query = query.filter(models.User.id != except_id)
    if query.first() is not None:
        raise api_error(409, "name_taken")


def _new_pin(user: models.User, pin: str) -> None:
    """Set a PIN; it ends every login made with the old one and lifts a lock."""
    user.pin_hash = auth.get_pin_hash(pin)
    user.token_version += 1
    user.failed_logins = 0
    user.lockouts = 0
    user.locked_until = None


@router.get("/config")
def public_config():
    """What the login page needs before anyone is logged in: the language for browsers in neither German nor English."""
    return {"default_language": config.default_language()}


@router.get("/users/public", response_model=list[schemas.UserPublic])
def public_users(db: Session = Depends(get_db)):
    """Names for the login screen."""
    return db.query(models.User).order_by(models.User.name_key).all()


@router.post("/token", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    user = auth.authenticate(db, body.name, body.pin)
    return {"access_token": auth.create_access_token(user)}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(auth.get_current_user)):
    return user_out(user)


@router.patch("/me", response_model=schemas.UserOut)
def update_me(
    body: schemas.MePatch, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    user.language = body.language
    db.commit()
    return user_out(user)


@router.post("/me/pin", status_code=204)
def change_pin(
    body: schemas.PinChange,
    response: Response,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if not auth.verify_pin(body.current_pin, user.pin_hash):
        raise api_error(400, "wrong_current_pin")
    _new_pin(user, body.new_pin)
    db.commit()
    # Other devices are logged out; this one carries on with a token for the new PIN
    response.headers["X-New-Token"] = auth.create_access_token(user)


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(_parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.query(models.User).order_by(models.User.name_key)]


@router.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(
    body: schemas.UserCreate, _parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)
):
    _check_name_free(db, body.name)
    user = models.User(
        name=body.name, name_key=auth.name_key(body.name), pin_hash=auth.get_pin_hash(body.pin), role=body.role
    )
    db.add(user)
    db.commit()
    return user_out(user)


@router.patch("/users/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    body: schemas.UserPatch,
    _parent: models.User = Depends(auth.require_parent),
    db: Session = Depends(get_db),
):
    user = _get_user(db, user_id)
    if body.name is not None:
        _check_name_free(db, body.name, except_id=user.id)
        user.name = body.name
        user.name_key = auth.name_key(body.name)
    if body.role is not None and body.role != user.role:
        # Without a parent nobody could reach the settings any more
        if user.role == models.UserRole.PARENT and _parent_count(db) == 1:
            raise api_error(400, "last_parent")
        user.role = body.role
    db.commit()
    return user_out(user)


@router.post("/users/{user_id}/pin", status_code=204)
def reset_pin(
    user_id: int,
    body: schemas.PinReset,
    _parent: models.User = Depends(auth.require_parent),
    db: Session = Depends(get_db),
):
    _new_pin(_get_user(db, user_id), body.pin)
    db.commit()


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, parent: models.User = Depends(auth.require_parent), db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    # A parent can only delete others, so the last parent always stays
    if user.id == parent.id:
        raise api_error(400, "cannot_delete_self")
    db.delete(user)
    db.commit()
