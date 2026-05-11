"""
FastAPI Authentication Dependencies

This module provides synchronous FastAPI dependency functions that protect
API routes by validating Bearer tokens and enforcing account-status rules.

Why two separate dependencies?
  - get_current_user       : Decodes the token and returns a lightweight
                             UserResponse Pydantic model.  It avoids a
                             database round-trip, making it suitable as a
                             cheap first-pass auth gate.
  - get_current_active_user: Wraps get_current_user and additionally
                             checks that the account is not disabled.

Important note on the returned object:
  `get_current_user` returns a UserResponse populated from the JWT payload.
  Only the `id` field is guaranteed to be accurate — other fields are set
  to placeholder values ("unknown", etc.) because the sync path does not
  query the database.  Routes that need real user data (profile, password
  change) must load the SQLAlchemy User row themselves using `id`:

      db.query(User).filter(User.id == current_user.id).first()

  See `_get_db_user` in app/main.py for the canonical pattern.

Token verification is delegated to User.verify_token(), which uses python-jose
to decode the HS256 signature without touching Redis or the database.
"""

from datetime import datetime
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.schemas.user import UserResponse
from app.models.user import User

# OAuth2 Bearer scheme that reads the token from the Authorization header.
# `tokenUrl` points to the Swagger UI "Authorize" button endpoint.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> UserResponse:
    """
    Synchronous FastAPI dependency: validate the Bearer token and return
    a minimal UserResponse.

    This function supports two token payload shapes produced by
    User.verify_token():
      1. A dict containing a full set of user fields (username, email, …)
         — constructed into a UserResponse directly.
      2. A dict with only a 'sub' key, or a bare UUID — both result in a
         UserResponse whose `id` is the real user UUID and all other fields
         are placeholder values.

    The placeholder-field design keeps the dependency synchronous and free
    of database I/O.  Callers that need a real User ORM object must perform
    an explicit DB lookup using `current_user.id`.

    Args:
        token: Raw JWT string extracted from the Authorization: Bearer header.

    Returns:
        A UserResponse whose `id` matches the authenticated user's UUID.

    Raises:
        HTTPException(401): If the token is missing, expired, or has an
                            invalid signature.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Delegate signature verification to the User model.
    # Returns a UUID or dict on success; None on any verification failure.
    token_data = User.verify_token(token)
    if token_data is None:
        raise credentials_exception

    try:
        # Case 1: Full payload dict — contains all user fields
        if isinstance(token_data, dict):
            if "username" in token_data:
                return UserResponse(**token_data)

            # Case 2: Minimal payload dict — only 'sub' (UUID string) present.
            # This is the common case when tokens are created by create_token().
            elif "sub" in token_data:
                return UserResponse(
                    id=token_data["sub"],
                    username="unknown",
                    email="unknown@example.com",
                    first_name="Unknown",
                    last_name="User",
                    is_active=True,
                    is_verified=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            else:
                raise credentials_exception

        # Case 3: verify_token() returned a bare UUID directly
        elif isinstance(token_data, UUID):
            return UserResponse(
                id=token_data,
                username="unknown",
                email="unknown@example.com",
                first_name="Unknown",
                last_name="User",
                is_active=True,
                is_verified=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        else:
            raise credentials_exception

    except Exception:
        raise credentials_exception


def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """
    FastAPI dependency: ensure the authenticated user's account is active.

    Wraps get_current_user and adds an account-status check.  Use this
    dependency (instead of get_current_user directly) on any route that
    should be inaccessible to disabled accounts.

    Args:
        current_user: UserResponse returned by get_current_user.

    Returns:
        The same UserResponse if the account is active.

    Raises:
        HTTPException(400): If current_user.is_active is False.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user
