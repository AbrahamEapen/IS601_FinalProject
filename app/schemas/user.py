"""
User Pydantic Schemas

This module defines the Pydantic schemas used for validating and serializing
user-related data across the API. Schemas serve as the contract between the
HTTP layer and the application's business logic:

- UserBase       : Shared fields inherited by creation and response schemas
- UserCreate     : Validates registration input, including password strength
- UserResponse   : Serializes ORM User objects for API responses (read-only)
- UserLogin      : Validates login credentials
- UserUpdate     : Validates partial profile-update requests (PATCH-style PUT)
- PasswordUpdate : Validates password-change requests, enforcing strength rules

Password strength rules (applied to both UserCreate and PasswordUpdate):
  - Minimum 8 characters
  - At least one uppercase letter
  - At least one lowercase letter
  - At least one digit
  - At least one special character from SPECIAL_CHARS
"""

from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator, field_validator

# Special characters accepted in passwords. Defined as a module-level constant
# so the same set is used by every validator that checks password strength.
SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"


class UserBase(BaseModel):
    """
    Shared base schema for user data.

    Contains the core identifying fields common to both user creation and
    user responses. Subclassed by UserCreate and UserResponse to avoid
    field duplication.

    Attributes:
        first_name : Given name, 1–50 characters.
        last_name  : Family name, 1–50 characters.
        email      : Valid email address (validated by EmailStr).
        username   : Unique login handle, 3–50 characters.
    """
    first_name: str = Field(min_length=1, max_length=50, example="John")
    last_name: str = Field(min_length=1, max_length=50, example="Doe")
    email: EmailStr = Field(example="john.doe@example.com")
    username: str = Field(min_length=3, max_length=50, example="johndoe")

    # Allow ORM model instances to be passed directly (from_orm / model_validate)
    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    """
    Schema for new user registration (POST /auth/register).

    Extends UserBase with password fields and enforces:
    1. Password confirmation — both fields must be identical.
    2. Password strength — uppercase, lowercase, digit, and special character
       are all required, and the minimum length is 8 characters.

    Attributes:
        password         : Plain-text password chosen by the user.
        confirm_password : Repeated password for typo prevention.

    Raises:
        ValueError: If passwords don't match or don't meet strength requirements.
    """
    password: str = Field(min_length=8, max_length=128, example="SecurePass123!")
    confirm_password: str = Field(min_length=8, max_length=128, example="SecurePass123!")

    @model_validator(mode="after")
    def verify_password_match(self) -> "UserCreate":
        """Ensure password and confirm_password are identical."""
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

    @model_validator(mode="after")
    def validate_password_strength(self) -> "UserCreate":
        """
        Enforce password complexity requirements.

        Checks (in order):
        - Minimum length (8 chars — already enforced by Field, but kept here
          as a belt-and-suspenders guard).
        - At least one uppercase ASCII letter.
        - At least one lowercase ASCII letter.
        - At least one decimal digit.
        - At least one character from SPECIAL_CHARS.

        Raises:
            ValueError: With a human-readable message describing the failing rule.
        """
        password = self.password
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(char.isupper() for char in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char.isdigit() for char in password):
            raise ValueError("Password must contain at least one digit")
        if not any(char in SPECIAL_CHARS for char in password):
            raise ValueError("Password must contain at least one special character")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "username": "johndoe",
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!",
            }
        }
    )


class UserResponse(BaseModel):
    """
    Schema for serializing user data in API responses.

    This is a read-only schema. It is never used for input validation.
    All timestamps are returned as timezone-aware datetime objects.

    Attributes:
        id          : UUID primary key of the user record.
        username    : Unique login handle.
        email       : Registered email address.
        first_name  : Given name.
        last_name   : Family name.
        is_active   : Whether the account is enabled.
        is_verified : Whether the user has confirmed their email address.
        created_at  : UTC timestamp of account creation.
        updated_at  : UTC timestamp of the most recent profile update.
    """
    id: UUID
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    # Enable reading values directly from SQLAlchemy ORM model attributes
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """
    Schema for user login requests (POST /auth/login).

    Accepts a username or email in the `username` field — the authentication
    logic in User.authenticate() queries both columns.

    Attributes:
        username : The user's login handle or email address.
        password : The user's plain-text password (never stored).
    """
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"username": "johndoe", "password": "SecurePass123!"}
        }
    )


class UserUpdate(BaseModel):
    """
    Schema for partial profile updates (PUT /users/me).

    All fields are optional, but at least one must be supplied — the
    `at_least_one_field` validator rejects empty payloads to prevent
    no-op requests from reaching the database.

    The route handler separately checks for username/email uniqueness
    before writing; this schema only validates the shape of the input.

    Attributes:
        first_name : New given name (optional).
        last_name  : New family name (optional).
        email      : New email address (optional, must be valid).
        username   : New login handle (optional, 3–50 characters).

    Raises:
        ValueError: If all four fields are None (empty update payload).
    """
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UserUpdate":
        """Reject requests where every field is None (nothing to update)."""
        if all(v is None for v in [self.first_name, self.last_name, self.email, self.username]):
            raise ValueError("At least one field must be provided for update")
        return self

    model_config = ConfigDict(from_attributes=True)


class PasswordUpdate(BaseModel):
    """
    Schema for password-change requests (PUT /users/me/password).

    Validates the entire password-change flow in one place:
    1. `validate_new_password_strength` (field validator) — runs on
       `new_password` alone before the model is fully constructed.
    2. `verify_passwords` (model validator) — runs after all fields are
       set and checks that the new password matches its confirmation and
       differs from the current password.

    The route handler is responsible for verifying that `current_password`
    matches the user's stored bcrypt hash; this schema does not have access
    to the database.

    Attributes:
        current_password    : The user's existing password (proof of identity).
        new_password        : The desired new password (must meet strength rules).
        confirm_new_password: Repeated new password for typo prevention.

    Raises:
        ValueError: If any strength rule, match check, or same-as-current
                    check fails.
    """
    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, v: str) -> str:
        """
        Enforce password complexity on the new password.

        Runs before the model-level validator so that strength errors are
        reported before the match/same-as-current checks.

        Args:
            v: The plain-text new password to validate.

        Returns:
            The validated password string (unchanged).

        Raises:
            ValueError: If any complexity requirement is not met.
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in SPECIAL_CHARS for c in v):
            raise ValueError("Password must contain at least one special character")
        return v

    @model_validator(mode="after")
    def verify_passwords(self) -> "PasswordUpdate":
        """
        Cross-field validation for the password change payload.

        Checks (in order):
        1. new_password == confirm_new_password (typo prevention).
        2. new_password != current_password (force an actual change).

        Raises:
            ValueError: With a descriptive message for each failing check.
        """
        if self.new_password != self.confirm_new_password:
            raise ValueError("New password and confirmation do not match")
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from current password")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_password": "OldPass123!",
                "new_password": "NewPass123!",
                "confirm_new_password": "NewPass123!",
            }
        }
    )
