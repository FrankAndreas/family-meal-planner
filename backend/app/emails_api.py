"""The addresses recipe mails may come from: each person's own, a parent's for anyone."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from . import auth, models, schemas
from .database import get_db
from .http_errors import api_error

router = APIRouter(tags=["emails"])


def _email_out(entry: models.UserEmail) -> schemas.EmailOut:
    return schemas.EmailOut(id=entry.id, user_id=entry.user_id, user_name=entry.user.name, address=entry.address)


@router.get("/emails", response_model=list[schemas.EmailOut])
def list_emails(all: bool = False, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    query = db.query(models.UserEmail)
    if not (all and user.is_parent):
        query = query.filter(models.UserEmail.user_id == user.id)
    return [_email_out(e) for e in query.order_by(models.UserEmail.address)]


@router.post("/emails", response_model=schemas.EmailOut, status_code=201)
def add_email(body: schemas.EmailIn, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    owner_id = body.user_id or user.id
    if not user.may_see(owner_id):
        raise api_error(403, "parents_only")
    if db.get(models.User, owner_id) is None:
        raise api_error(404, "user_not_found")
    if db.query(models.UserEmail).filter(models.UserEmail.address == body.address).first():
        raise api_error(409, "email_taken")
    entry = models.UserEmail(user_id=owner_id, address=body.address)
    db.add(entry)
    db.commit()
    return _email_out(entry)


@router.delete("/emails/{email_id}", status_code=204)
def delete_email(email_id: int, user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    entry = db.get(models.UserEmail, email_id)
    if entry is None or not user.may_see(entry.user_id):
        raise api_error(404, "email_not_found")
    db.delete(entry)
    db.commit()
