# app/schemas/user.py

from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator, field_validator

SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"


class UserBase(BaseModel):
    """Base user schema with common fields"""
    first_name: str = Field(min_length=1, max_length=50, example="John")
    last_name: str = Field(min_length=1, max_length=50, example="Doe")
    email: EmailStr = Field(example="john.doe@example.com")
    username: str = Field(min_length=3, max_length=50, example="johndoe")
    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    """Schema for user creation with password validation"""
    password: str = Field(min_length=8, max_length=128, example="SecurePass123!")
    confirm_password: str = Field(min_length=8, max_length=128, example="SecurePass123!")

    @model_validator(mode="after")
    def verify_password_match(self) -> "UserCreate":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

    @model_validator(mode="after")
    def validate_password_strength(self) -> "UserCreate":
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
    """Schema for user response data"""
    id: UUID
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """Schema for user login"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"username": "johndoe", "password": "SecurePass123!"}
        }
    )


class UserUpdate(BaseModel):
    """Schema for updating profile info. At least one field must be provided."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UserUpdate":
        if all(v is None for v in [self.first_name, self.last_name, self.email, self.username]):
            raise ValueError("At least one field must be provided for update")
        return self

    model_config = ConfigDict(from_attributes=True)


class PasswordUpdate(BaseModel):
    """Schema for password change. Validates strength of the new password."""
    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, v: str) -> str:
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
