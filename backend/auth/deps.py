"""FastAPI dependencies for JWT-based authentication."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.auth.security import decode_access_token
from backend.db.base import get_db
from backend.db.models import User

_required_scheme = HTTPBearer(auto_error=True)
_optional_scheme = HTTPBearer(auto_error=False)


def _user_from_token(token: str, db: Session) -> User | None:
    """Decode a JWT and return the matching User row, or None if invalid."""
    payload = decode_access_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None
    return db.get(User, user_id)


def get_current_user_required(
    credentials: HTTPAuthorizationCredentials = Depends(_required_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user, raising 401 if the token is missing or invalid."""
    user = _user_from_token(credentials.credentials, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_scheme),
) -> User | None:
    """Return the authenticated user if a valid token is present, else None.

    Used by public endpoints that still want to link saved rows to a user
    when one happens to be logged in.
    """
    if credentials is None:
        return None
    return _user_from_token(credentials.credentials, db)
