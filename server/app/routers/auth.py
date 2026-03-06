from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.limits import limiter
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/register", status_code=201, response_model=UserOut)
@limiter.limit("10/minute")
def register(request: Request, body: RegisterIn, db: Session = Depends(get_db)):
    exists = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    # Same message whether email or password is wrong — avoids user enumeration.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
