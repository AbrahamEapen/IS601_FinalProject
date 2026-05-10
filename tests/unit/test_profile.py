# tests/unit/test_profile.py
"""
Unit tests for profile-related schema validation and password change logic.
"""
import pytest
from pydantic import ValidationError

from app.schemas.user import UserUpdate, PasswordUpdate
from app.models.user import User


# =============================================================================
# UserUpdate schema tests
# =============================================================================

class TestUserUpdateSchema:
    def test_valid_update_first_name_only(self):
        data = UserUpdate(first_name="Alice")
        assert data.first_name == "Alice"

    def test_valid_update_last_name_only(self):
        data = UserUpdate(last_name="Smith")
        assert data.last_name == "Smith"

    def test_valid_update_username_only(self):
        data = UserUpdate(username="newuser")
        assert data.username == "newuser"

    def test_valid_update_email_only(self):
        data = UserUpdate(email="new@example.com")
        assert data.email == "new@example.com"

    def test_valid_update_all_fields(self):
        data = UserUpdate(
            first_name="Bob",
            last_name="Jones",
            email="bob@example.com",
            username="bobjones",
        )
        assert data.first_name == "Bob"
        assert data.last_name == "Jones"

    def test_empty_update_raises(self):
        with pytest.raises(ValidationError, match="At least one field must be provided"):
            UserUpdate()

    def test_all_none_raises(self):
        with pytest.raises(ValidationError, match="At least one field must be provided"):
            UserUpdate(first_name=None, last_name=None, email=None, username=None)

    def test_username_too_short_raises(self):
        with pytest.raises(ValidationError):
            UserUpdate(username="ab")

    def test_username_too_long_raises(self):
        with pytest.raises(ValidationError):
            UserUpdate(username="a" * 51)

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            UserUpdate(email="not-an-email")

    def test_first_name_empty_string_raises(self):
        with pytest.raises(ValidationError):
            UserUpdate(first_name="")

    def test_partial_update_leaves_other_fields_none(self):
        data = UserUpdate(username="newname")
        assert data.first_name is None
        assert data.last_name is None
        assert data.email is None


# =============================================================================
# PasswordUpdate schema tests
# =============================================================================

class TestPasswordUpdateSchema:
    VALID_CURRENT = "OldPass123!"
    VALID_NEW = "NewPass456@"

    def test_valid_password_update(self):
        data = PasswordUpdate(
            current_password=self.VALID_CURRENT,
            new_password=self.VALID_NEW,
            confirm_new_password=self.VALID_NEW,
        )
        assert data.new_password == self.VALID_NEW

    def test_mismatched_confirm_raises(self):
        with pytest.raises(ValidationError, match="do not match"):
            PasswordUpdate(
                current_password=self.VALID_CURRENT,
                new_password=self.VALID_NEW,
                confirm_new_password="DifferentPass1!",
            )

    def test_same_as_current_raises(self):
        with pytest.raises(ValidationError, match="different from current"):
            PasswordUpdate(
                current_password=self.VALID_CURRENT,
                new_password=self.VALID_CURRENT,
                confirm_new_password=self.VALID_CURRENT,
            )

    def test_new_password_too_short_raises(self):
        with pytest.raises(ValidationError):
            PasswordUpdate(
                current_password=self.VALID_CURRENT,
                new_password="Sh0rt!",
                confirm_new_password="Sh0rt!",
            )

    def test_new_password_no_uppercase_raises(self):
        with pytest.raises(ValidationError, match="uppercase"):
            PasswordUpdate(
                current_password=self.VALID_CURRENT,
                new_password="newpass123!",
                confirm_new_password="newpass123!",
            )

    def test_new_password_no_lowercase_raises(self):
        with pytest.raises(ValidationError, match="lowercase"):
            PasswordUpdate(
                current_password=self.VALID_CURRENT,
                new_password="NEWPASS123!",
                confirm_new_password="NEWPASS123!",
            )

    def test_new_password_no_digit_raises(self):
        with pytest.raises(ValidationError, match="digit"):
            PasswordUpdate(
                current_password=self.VALID_CURRENT,
                new_password="NewPassWord!",
                confirm_new_password="NewPassWord!",
            )

    def test_new_password_no_special_char_raises(self):
        with pytest.raises(ValidationError, match="special character"):
            PasswordUpdate(
                current_password=self.VALID_CURRENT,
                new_password="NewPass1234",
                confirm_new_password="NewPass1234",
            )


# =============================================================================
# User model password logic tests
# =============================================================================

class TestUserPasswordLogic:
    def test_hash_password_returns_different_string(self):
        plain = "TestPass123!"
        hashed = User.hash_password(plain)
        assert hashed != plain

    def test_hash_password_is_bcrypt(self):
        hashed = User.hash_password("TestPass123!")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_verify_password_correct(self):
        plain = "TestPass123!"
        hashed = User.hash_password(plain)
        user = User(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            username="testuser",
            password=hashed,
        )
        assert user.verify_password(plain) is True

    def test_verify_password_wrong(self):
        hashed = User.hash_password("TestPass123!")
        user = User(
            first_name="Test",
            last_name="User",
            email="test2@example.com",
            username="testuser2",
            password=hashed,
        )
        assert user.verify_password("WrongPass456@") is False

    def test_two_hashes_of_same_password_differ(self):
        plain = "TestPass123!"
        h1 = User.hash_password(plain)
        h2 = User.hash_password(plain)
        assert h1 != h2  # bcrypt uses random salt

    def test_update_method_sets_fields(self):
        user = User(
            first_name="Old",
            last_name="Name",
            email="old@example.com",
            username="olduser",
            password="hashed",
        )
        user.update(first_name="New", last_name="Name2")
        assert user.first_name == "New"
        assert user.last_name == "Name2"
