"""
JWT Authentication Utilities

This module provides the low-level cryptographic building blocks for the
application's token-based authentication system:

- Password hashing  : bcrypt via passlib (verify_password, get_password_hash)
- Token creation    : HS256-signed JWTs with configurable expiry (create_token)
- Token decoding    : Signature verification, type checking, blacklist check
                      (decode_token)
- Current-user dep  : FastAPI dependency that decodes the Bearer token and
                      returns the authenticated User ORM object (get_current_user)

Token structure (JWT payload claims):
  sub  — string UUID of the authenticated user
  type — "access" | "refresh" (maps to TokenType enum)
  exp  — expiration timestamp (UTC)
  iat  — issued-at timestamp (UTC)
  jti  — random 32-hex-char nonce used for blacklisting on logout

Secrets:
  Access tokens  → signed with JWT_SECRET_KEY
  Refresh tokens → signed with JWT_REFRESH_SECRET_KEY

Both keys and token lifetimes are read from app.core.config.Settings, which
sources them from environment variables (or a .env file).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from uuid import UUID
import secrets

from app.core.config import get_settings
from app.auth.redis import add_to_blacklist, is_blacklisted
from app.schemas.token import TokenType
from app.database import get_db
from sqlalchemy.orm import Session
from app.models.user import User

# Load application configuration (JWT secrets, token lifetimes, bcrypt rounds)
settings = get_settings()

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

# CryptContext wraps passlib's bcrypt handler.  `deprecated="auto"` means
# older hashes that used fewer rounds will be flagged for re-hashing on the
# next successful login (future-proofing).  The number of bcrypt work-factor
# rounds is configurable via BCRYPT_ROUNDS (default 12; use 4 in CI for speed).
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS
)

# OAuth2 Bearer scheme — FastAPI reads the token from the Authorization header
# and passes it to any function that declares `token: str = Depends(oauth2_scheme)`.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare a plain-text password against a bcrypt hash.

    Uses passlib's constant-time comparison to prevent timing attacks.

    Args:
        plain_password   : The password supplied by the user at login.
        hashed_password  : The bcrypt hash stored in the database.

    Returns:
        True if the password matches the hash; False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a plain-text password with bcrypt.

    The resulting string includes the algorithm identifier, work factor, and
    salt, making it self-contained for later verification.

    Args:
        password: The plain-text password to hash.

    Returns:
        A bcrypt hash string (e.g. "$2b$12$...").
    """
    return pwd_context.hash(password)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_token(
    user_id: Union[str, UUID],
    token_type: TokenType,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a signed JWT access or refresh token.

    The token payload includes:
      - sub  : string representation of the user's UUID (subject)
      - type : "access" or "refresh" (prevents cross-type token reuse)
      - exp  : expiration datetime in UTC
      - iat  : issued-at datetime in UTC
      - jti  : 32-character random hex nonce (JSON Token ID) for blacklisting

    Args:
        user_id      : The UUID of the authenticated user.
        token_type   : TokenType.ACCESS or TokenType.REFRESH — determines
                       the signing secret and the default expiry period.
        expires_delta: Optional override for token lifetime.  When omitted,
                       access tokens expire after ACCESS_TOKEN_EXPIRE_MINUTES
                       and refresh tokens after REFRESH_TOKEN_EXPIRE_DAYS.

    Returns:
        A signed JWT string ready to be returned in the API response.

    Raises:
        HTTPException(500): If the JWT library fails to encode the token
                            (e.g. bad key format).
    """
    # Determine expiration time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        if token_type == TokenType.ACCESS:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )

    # Normalize UUID to string — jose requires JSON-serializable claims
    if isinstance(user_id, UUID):
        user_id = str(user_id)

    to_encode = {
        "sub": user_id,
        "type": token_type.value,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_hex(16),  # 32-char nonce for blacklist support
    }

    # Select the correct secret based on token type
    secret = (
        settings.JWT_SECRET_KEY
        if token_type == TokenType.ACCESS
        else settings.JWT_REFRESH_SECRET_KEY
    )

    try:
        return jwt.encode(to_encode, secret, algorithm=settings.ALGORITHM)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create token: {str(e)}"
        )


# ---------------------------------------------------------------------------
# Token decoding
# ---------------------------------------------------------------------------

async def decode_token(
    token: str,
    token_type: TokenType,
    verify_exp: bool = True
) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Performs three layers of validation:
    1. Signature + expiry — jose verifies the HMAC signature and, when
       verify_exp=True, rejects tokens past their `exp` claim.
    2. Type check — the `type` claim must match `token_type` to prevent
       an access token being used where a refresh token is expected (and
       vice versa).
    3. Blacklist check — the `jti` nonce is looked up in Redis.  Tokens
       are blacklisted on logout so that stolen tokens cannot be reused
       within their remaining validity window.

    Args:
        token      : Raw JWT string from the Authorization header.
        token_type : Expected token type (ACCESS or REFRESH).
        verify_exp : Whether to enforce expiry.  Pass False only when
                     issuing a new access token from a refresh token flow
                     (the refresh endpoint may receive an expired access token).

    Returns:
        The decoded JWT payload as a plain dictionary.

    Raises:
        HTTPException(401): If the signature is invalid, the token is expired,
                            the type claim is wrong, or the jti is blacklisted.
    """
    try:
        # Choose the correct signing secret for this token type
        secret = (
            settings.JWT_SECRET_KEY
            if token_type == TokenType.ACCESS
            else settings.JWT_REFRESH_SECRET_KEY
        )

        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": verify_exp}
        )

        # Reject tokens of the wrong type (e.g. refresh token presented as access)
        if payload.get("type") != token_type.value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Reject tokens whose jti has been added to the Redis blacklist (logout)
        if await is_blacklisted(payload["jti"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# FastAPI dependency — current user
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency: decode the Bearer token and return the User ORM object.

    This is the async counterpart of the sync dependency in dependencies.py.
    It performs a full database lookup to return the live SQLAlchemy User row,
    which is required when callers need to read or write user attributes.

    Flow:
      1. Extract the raw token string from the Authorization header
         (handled by oauth2_scheme).
      2. Decode and validate the token via decode_token (signature, expiry,
         type, blacklist).
      3. Query the database for the user whose UUID matches the `sub` claim.
      4. Reject inactive accounts with a 400 error.

    Args:
        token : Bearer token injected by FastAPI's OAuth2PasswordBearer.
        db    : SQLAlchemy session injected by the get_db dependency.

    Returns:
        The authenticated, active User ORM instance.

    Raises:
        HTTPException(401): If the token is invalid or the user is not found.
        HTTPException(400): If the account is marked inactive.
    """
    try:
        payload = await decode_token(token, TokenType.ACCESS)
        user_id = payload["sub"]

        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        return user

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
