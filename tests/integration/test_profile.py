# tests/integration/test_profile.py
"""
Integration tests for the user profile and password-change API routes.

Routes under test:
  GET  /users/me
  PUT  /users/me
  PUT  /users/me/password
"""
import pytest
import requests
from faker import Faker

fake = Faker()
Faker.seed(99999)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_user(suffix: str = "") -> dict:
    return {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": f"profile_test_{suffix}_{fake.unique.uuid4()}@example.com",
        "username": f"pt_{suffix}_{fake.unique.numerify('####')}",
        "password": "SecurePass123!",
        "confirm_password": "SecurePass123!",
    }


def _register_and_login(base_url: str, user_data: dict) -> dict:
    """Register a user and return the full login response (tokens + user info)."""
    r = requests.post(f"{base_url}/auth/register", json=user_data)
    assert r.status_code == 201, f"Register failed: {r.text}"

    login = requests.post(
        f"{base_url}/auth/login",
        json={"username": user_data["username"], "password": user_data["password"]},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    return login.json()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_url(fastapi_server: str) -> str:
    return fastapi_server.rstrip("/")


@pytest.fixture
def registered_user(base_url: str):
    """Returns (user_data, token_response) for a freshly registered user."""
    user_data = _unique_user("reg")
    token_resp = _register_and_login(base_url, user_data)
    return user_data, token_resp


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------

class TestGetProfile:
    def test_returns_own_profile(self, base_url, registered_user):
        user_data, token_resp = registered_user
        r = requests.get(f"{base_url}/users/me", headers=_auth_headers(token_resp["access_token"]))
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == user_data["username"]
        assert body["email"] == user_data["email"]
        assert body["first_name"] == user_data["first_name"]
        assert body["last_name"] == user_data["last_name"]
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body
        assert "password" not in body  # never expose raw password

    def test_unauthenticated_returns_401(self, base_url):
        r = requests.get(f"{base_url}/users/me")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, base_url):
        r = requests.get(f"{base_url}/users/me", headers={"Authorization": "Bearer badtoken"})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# PUT /users/me
# ---------------------------------------------------------------------------

class TestUpdateProfile:
    def test_update_first_name(self, base_url, registered_user):
        user_data, token_resp = registered_user
        r = requests.put(
            f"{base_url}/users/me",
            json={"first_name": "UpdatedFirst"},
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 200
        assert r.json()["first_name"] == "UpdatedFirst"

    def test_update_last_name(self, base_url, registered_user):
        user_data, token_resp = registered_user
        r = requests.put(
            f"{base_url}/users/me",
            json={"last_name": "UpdatedLast"},
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 200
        assert r.json()["last_name"] == "UpdatedLast"

    def test_update_username(self, base_url, registered_user):
        _, token_resp = registered_user
        new_username = f"newuser_{fake.unique.numerify('####')}"
        r = requests.put(
            f"{base_url}/users/me",
            json={"username": new_username},
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 200
        assert r.json()["username"] == new_username

    def test_update_email(self, base_url, registered_user):
        _, token_resp = registered_user
        new_email = f"updated_{fake.unique.uuid4()}@example.com"
        r = requests.put(
            f"{base_url}/users/me",
            json={"email": new_email},
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 200
        assert r.json()["email"] == new_email

    def test_update_multiple_fields(self, base_url, registered_user):
        _, token_resp = registered_user
        payload = {
            "first_name": "Multi",
            "last_name": "Update",
            "username": f"multi_{fake.unique.numerify('####')}",
        }
        r = requests.put(
            f"{base_url}/users/me",
            json=payload,
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["first_name"] == "Multi"
        assert body["last_name"] == "Update"
        assert body["username"] == payload["username"]

    def test_update_persists_in_db(self, base_url, registered_user):
        _, token_resp = registered_user
        headers = _auth_headers(token_resp["access_token"])
        new_name = "PersistTest"
        requests.put(f"{base_url}/users/me", json={"first_name": new_name}, headers=headers)
        # Re-fetch and check persistence
        r = requests.get(f"{base_url}/users/me", headers=headers)
        assert r.json()["first_name"] == new_name

    def test_empty_body_returns_422(self, base_url, registered_user):
        _, token_resp = registered_user
        r = requests.put(
            f"{base_url}/users/me",
            json={},
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 422

    def test_duplicate_username_returns_409(self, base_url, registered_user):
        user_data, token_resp = registered_user
        # Register a second user
        other = _unique_user("dup")
        _register_and_login(base_url, other)

        # Try to claim second user's username
        r = requests.put(
            f"{base_url}/users/me",
            json={"username": other["username"]},
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 409

    def test_duplicate_email_returns_409(self, base_url, registered_user):
        _, token_resp = registered_user
        other = _unique_user("dup2")
        _register_and_login(base_url, other)

        r = requests.put(
            f"{base_url}/users/me",
            json={"email": other["email"]},
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 409

    def test_unauthenticated_returns_401(self, base_url):
        r = requests.put(f"{base_url}/users/me", json={"first_name": "X"})
        assert r.status_code == 401

    def test_username_too_short_returns_422(self, base_url, registered_user):
        _, token_resp = registered_user
        r = requests.put(
            f"{base_url}/users/me",
            json={"username": "ab"},
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 422

    def test_invalid_email_returns_422(self, base_url, registered_user):
        _, token_resp = registered_user
        r = requests.put(
            f"{base_url}/users/me",
            json={"email": "not-an-email"},
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# PUT /users/me/password
# ---------------------------------------------------------------------------

class TestChangePassword:
    OLD_PASS = "SecurePass123!"
    NEW_PASS = "NewSecure456@"

    def test_successful_password_change(self, base_url, registered_user):
        user_data, token_resp = registered_user
        r = requests.put(
            f"{base_url}/users/me/password",
            json={
                "current_password": self.OLD_PASS,
                "new_password": self.NEW_PASS,
                "confirm_new_password": self.NEW_PASS,
            },
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 204

    def test_new_password_works_for_login(self, base_url, registered_user):
        user_data, token_resp = registered_user
        requests.put(
            f"{base_url}/users/me/password",
            json={
                "current_password": self.OLD_PASS,
                "new_password": self.NEW_PASS,
                "confirm_new_password": self.NEW_PASS,
            },
            headers=_auth_headers(token_resp["access_token"]),
        )
        # Login with new password should succeed
        login = requests.post(
            f"{base_url}/auth/login",
            json={"username": user_data["username"], "password": self.NEW_PASS},
        )
        assert login.status_code == 200

    def test_old_password_rejected_after_change(self, base_url, registered_user):
        user_data, token_resp = registered_user
        requests.put(
            f"{base_url}/users/me/password",
            json={
                "current_password": self.OLD_PASS,
                "new_password": self.NEW_PASS,
                "confirm_new_password": self.NEW_PASS,
            },
            headers=_auth_headers(token_resp["access_token"]),
        )
        # Login with old password should fail
        login = requests.post(
            f"{base_url}/auth/login",
            json={"username": user_data["username"], "password": self.OLD_PASS},
        )
        assert login.status_code == 401

    def test_wrong_current_password_returns_400(self, base_url, registered_user):
        _, token_resp = registered_user
        r = requests.put(
            f"{base_url}/users/me/password",
            json={
                "current_password": "WrongOld999!",
                "new_password": self.NEW_PASS,
                "confirm_new_password": self.NEW_PASS,
            },
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 400

    def test_mismatched_confirm_returns_422(self, base_url, registered_user):
        _, token_resp = registered_user
        r = requests.put(
            f"{base_url}/users/me/password",
            json={
                "current_password": self.OLD_PASS,
                "new_password": self.NEW_PASS,
                "confirm_new_password": "Different456@",
            },
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 422

    def test_same_as_current_returns_422(self, base_url, registered_user):
        _, token_resp = registered_user
        r = requests.put(
            f"{base_url}/users/me/password",
            json={
                "current_password": self.OLD_PASS,
                "new_password": self.OLD_PASS,
                "confirm_new_password": self.OLD_PASS,
            },
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 422

    def test_weak_new_password_returns_422(self, base_url, registered_user):
        _, token_resp = registered_user
        r = requests.put(
            f"{base_url}/users/me/password",
            json={
                "current_password": self.OLD_PASS,
                "new_password": "weakpassword",
                "confirm_new_password": "weakpassword",
            },
            headers=_auth_headers(token_resp["access_token"]),
        )
        assert r.status_code == 422

    def test_unauthenticated_returns_401(self, base_url):
        r = requests.put(
            f"{base_url}/users/me/password",
            json={
                "current_password": self.OLD_PASS,
                "new_password": self.NEW_PASS,
                "confirm_new_password": self.NEW_PASS,
            },
        )
        assert r.status_code == 401
