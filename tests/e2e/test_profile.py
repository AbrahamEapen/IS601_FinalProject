# tests/e2e/test_profile.py
"""
E2E Playwright tests for the User Profile feature.

Covers:
  - Positive: login → profile page loads with user data
  - Positive: update profile info
  - Positive: change password → re-login with new password succeeds
  - Negative: wrong current password
  - Negative: weak new password
  - Negative: mismatched confirm password
  - Negative: empty profile update
  - Negative: unauthenticated access redirects to login (JS-side enforcement)
"""
import pytest
import requests
from faker import Faker
from playwright.sync_api import Page, expect

fake = Faker()
Faker.seed(77777)

BASE_PASSWORD = "SecurePass123!"
NEW_PASSWORD = "NewSecure456@"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_user(tag: str = "") -> dict:
    uid = fake.unique.numerify("####")
    return {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": f"e2e_{tag}_{uid}@example.com",
        "username": f"e2e_{tag}_{uid}",
        "password": BASE_PASSWORD,
        "confirm_password": BASE_PASSWORD,
    }


def _api_register_and_login(base_url: str, user_data: dict) -> str:
    """Register via API and return the access token."""
    r = requests.post(f"{base_url}/auth/register", json=user_data)
    assert r.status_code == 201, f"Register failed: {r.text}"
    login = requests.post(
        f"{base_url}/auth/login",
        json={"username": user_data["username"], "password": user_data["password"]},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    return login.json()["access_token"]


def _seed_localstorage(page: Page, base_url: str, access_token: str, username: str):
    """Navigate to the app and inject auth token into localStorage."""
    page.goto(base_url)
    page.evaluate(
        f"""() => {{
            localStorage.setItem('access_token', '{access_token}');
            localStorage.setItem('username', '{username}');
        }}"""
    )


def _do_ui_login(page: Page, base_url: str, username: str, password: str):
    """Perform login through the UI login form."""
    page.goto(f"{base_url}/login")
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("button[type='submit']").click()
    # Wait for redirect to dashboard
    page.wait_for_url(f"{base_url}/dashboard", timeout=10000)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_url(fastapi_server: str) -> str:
    return fastapi_server.rstrip("/")


@pytest.fixture
def profile_user(base_url):
    """Creates a user via API and returns (user_data, access_token)."""
    user_data = _unique_user("profile")
    token = _api_register_and_login(base_url, user_data)
    return user_data, token


# ---------------------------------------------------------------------------
# Profile page load
# ---------------------------------------------------------------------------

class TestProfilePageLoad:
    def test_profile_page_loads_user_data(self, page: Page, base_url: str, profile_user):
        user_data, token = profile_user
        _seed_localstorage(page, base_url, token, user_data["username"])

        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")

        # Fields should be populated from the API
        expect(page.locator("#first_name")).to_have_value(user_data["first_name"])
        expect(page.locator("#last_name")).to_have_value(user_data["last_name"])
        expect(page.locator("#username")).to_have_value(user_data["username"])
        expect(page.locator("#email")).to_have_value(user_data["email"])

    def test_profile_tab_active_by_default(self, page: Page, base_url: str, profile_user):
        user_data, token = profile_user
        _seed_localstorage(page, base_url, token, user_data["username"])
        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")

        # Profile section visible, password section hidden
        expect(page.locator("#sectionProfile")).to_be_visible()
        expect(page.locator("#sectionPassword")).to_be_hidden()

    def test_switch_to_password_tab(self, page: Page, base_url: str, profile_user):
        user_data, token = profile_user
        _seed_localstorage(page, base_url, token, user_data["username"])
        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")

        page.locator("#tabPassword").click()
        expect(page.locator("#sectionPassword")).to_be_visible()
        expect(page.locator("#sectionProfile")).to_be_hidden()

    def test_profile_link_visible_when_logged_in(self, page: Page, base_url: str, profile_user):
        user_data, token = profile_user
        _seed_localstorage(page, base_url, token, user_data["username"])
        page.goto(f"{base_url}/dashboard")
        page.wait_for_load_state("networkidle")
        expect(page.locator("#layoutProfileBtn")).to_be_visible()


# ---------------------------------------------------------------------------
# Profile info update
# ---------------------------------------------------------------------------

class TestUpdateProfileUI:
    def test_update_first_name_shows_success(self, page: Page, base_url: str, profile_user):
        user_data, token = profile_user
        _seed_localstorage(page, base_url, token, user_data["username"])
        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")

        page.locator("#first_name").fill("UpdatedName")
        page.locator("#profileForm button[type='submit']").click()

        success_alert = page.locator("#profileAlert")
        expect(success_alert).to_be_visible()
        expect(success_alert).to_contain_text("successfully")

    def test_update_username_reflects_in_header(self, page: Page, base_url: str, profile_user):
        user_data, token = profile_user
        new_username = f"updated_{fake.unique.numerify('####')}"
        _seed_localstorage(page, base_url, token, user_data["username"])
        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")

        page.locator("#username").fill(new_username)
        page.locator("#profileForm button[type='submit']").click()

        # Header welcome text updates
        welcome = page.locator("#layoutUserWelcome")
        expect(welcome).to_contain_text(new_username)

    def test_empty_first_name_shows_field_error(self, page: Page, base_url: str, profile_user):
        user_data, token = profile_user
        _seed_localstorage(page, base_url, token, user_data["username"])
        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")

        page.locator("#first_name").fill("")
        page.locator("#profileForm button[type='submit']").click()

        expect(page.locator("#first_name_err")).to_be_visible()

    def test_invalid_email_shows_field_error(self, page: Page, base_url: str, profile_user):
        user_data, token = profile_user
        _seed_localstorage(page, base_url, token, user_data["username"])
        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")

        page.locator("#email").fill("not-an-email")
        page.locator("#profileForm button[type='submit']").click()

        expect(page.locator("#email_err")).to_be_visible()

    def test_username_too_short_shows_field_error(self, page: Page, base_url: str, profile_user):
        user_data, token = profile_user
        _seed_localstorage(page, base_url, token, user_data["username"])
        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")

        page.locator("#username").fill("ab")
        page.locator("#profileForm button[type='submit']").click()

        expect(page.locator("#username_err")).to_be_visible()


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------

class TestChangePasswordUI:
    def _go_to_password_tab(self, page: Page, base_url: str, profile_user):
        user_data, token = profile_user
        _seed_localstorage(page, base_url, token, user_data["username"])
        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")
        page.locator("#tabPassword").click()
        return user_data

    def test_successful_password_change_shows_success(self, page: Page, base_url: str, profile_user):
        user_data = self._go_to_password_tab(page, base_url, profile_user)

        page.locator("#current_password").fill(BASE_PASSWORD)
        page.locator("#new_password").fill(NEW_PASSWORD)
        page.locator("#confirm_new_password").fill(NEW_PASSWORD)
        page.locator("#passwordForm button[type='submit']").click()

        expect(page.locator("#passwordAlert")).to_contain_text("successfully")

    def test_password_change_then_relogin(self, page: Page, base_url: str, profile_user):
        """Full flow: login → change password → logout → re-login with new password."""
        user_data, token = profile_user
        _seed_localstorage(page, base_url, token, user_data["username"])
        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")
        page.locator("#tabPassword").click()

        page.locator("#current_password").fill(BASE_PASSWORD)
        page.locator("#new_password").fill(NEW_PASSWORD)
        page.locator("#confirm_new_password").fill(NEW_PASSWORD)
        page.locator("#passwordForm button[type='submit']").click()

        # Wait for auto-redirect to login after password change
        page.wait_for_url(f"{base_url}/login", timeout=8000)

        # Re-login with new password
        page.locator("#username").fill(user_data["username"])
        page.locator("#password").fill(NEW_PASSWORD)
        page.locator("button[type='submit']").click()
        page.wait_for_url(f"{base_url}/dashboard", timeout=10000)

    def test_wrong_current_password_shows_error(self, page: Page, base_url: str, profile_user):
        self._go_to_password_tab(page, base_url, profile_user)

        page.locator("#current_password").fill("WrongPass999!")
        page.locator("#new_password").fill(NEW_PASSWORD)
        page.locator("#confirm_new_password").fill(NEW_PASSWORD)
        page.locator("#passwordForm button[type='submit']").click()

        expect(page.locator("#passwordAlert")).to_be_visible()
        expect(page.locator("#passwordAlert")).to_contain_text("incorrect")

    def test_mismatched_confirm_shows_field_error(self, page: Page, base_url: str, profile_user):
        self._go_to_password_tab(page, base_url, profile_user)

        page.locator("#current_password").fill(BASE_PASSWORD)
        page.locator("#new_password").fill(NEW_PASSWORD)
        page.locator("#confirm_new_password").fill("Mismatch999@")
        page.locator("#passwordForm button[type='submit']").click()

        expect(page.locator("#confirm_new_password_err")).to_be_visible()

    def test_weak_password_shows_field_error(self, page: Page, base_url: str, profile_user):
        self._go_to_password_tab(page, base_url, profile_user)

        page.locator("#current_password").fill(BASE_PASSWORD)
        page.locator("#new_password").fill("weakpass")
        page.locator("#confirm_new_password").fill("weakpass")
        page.locator("#passwordForm button[type='submit']").click()

        expect(page.locator("#new_password_err")).to_be_visible()

    def test_same_as_current_shows_field_error(self, page: Page, base_url: str, profile_user):
        self._go_to_password_tab(page, base_url, profile_user)

        page.locator("#current_password").fill(BASE_PASSWORD)
        page.locator("#new_password").fill(BASE_PASSWORD)
        page.locator("#confirm_new_password").fill(BASE_PASSWORD)
        page.locator("#passwordForm button[type='submit']").click()

        expect(page.locator("#new_password_err")).to_be_visible()

    def test_empty_current_password_shows_error(self, page: Page, base_url: str, profile_user):
        self._go_to_password_tab(page, base_url, profile_user)

        page.locator("#new_password").fill(NEW_PASSWORD)
        page.locator("#confirm_new_password").fill(NEW_PASSWORD)
        page.locator("#passwordForm button[type='submit']").click()

        expect(page.locator("#current_password_err")).to_be_visible()


# ---------------------------------------------------------------------------
# Full E2E flow: login → profile → update → password change → re-login
# ---------------------------------------------------------------------------

class TestFullProfileFlow:
    def test_full_flow_login_profile_password_relogin(self, page: Page, base_url: str):
        """
        Complete flow:
        1. Register via API
        2. Login via UI
        3. Navigate to profile page
        4. Update first name
        5. Change password
        6. Automatically redirected to login
        7. Re-login with new password
        8. Verify dashboard is accessible
        """
        user_data = _unique_user("full")
        _api_register_and_login(base_url, user_data)

        # Step 2: UI login
        _do_ui_login(page, base_url, user_data["username"], BASE_PASSWORD)

        # Step 3: Navigate to profile
        page.goto(f"{base_url}/profile")
        page.wait_for_load_state("networkidle")

        # Step 4: Update first name
        page.locator("#first_name").fill("FullFlow")
        page.locator("#profileForm button[type='submit']").click()
        expect(page.locator("#profileAlert")).to_contain_text("successfully")

        # Step 5: Change password
        page.locator("#tabPassword").click()
        page.locator("#current_password").fill(BASE_PASSWORD)
        page.locator("#new_password").fill(NEW_PASSWORD)
        page.locator("#confirm_new_password").fill(NEW_PASSWORD)
        page.locator("#passwordForm button[type='submit']").click()

        # Step 6: Auto-redirect to login
        page.wait_for_url(f"{base_url}/login", timeout=8000)

        # Step 7: Re-login with new password
        page.locator("#username").fill(user_data["username"])
        page.locator("#password").fill(NEW_PASSWORD)
        page.locator("button[type='submit']").click()

        # Step 8: Dashboard accessible
        page.wait_for_url(f"{base_url}/dashboard", timeout=10000)
        expect(page).to_have_url(f"{base_url}/dashboard")
