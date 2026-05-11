"""
Integration tests for calculation BREAD HTTP endpoints.
Covers POST /calculations, GET /calculations, GET /calculations/{id},
PUT /calculations/{id}, DELETE /calculations/{id}.
"""
import pytest
import requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _post(server, headers, payload):
    return requests.post(f"{server}calculations", json=payload, headers=headers)

def _list(server, headers):
    return requests.get(f"{server}calculations", headers=headers)

def _get(server, headers, calc_id):
    return requests.get(f"{server}calculations/{calc_id}", headers=headers)

def _put(server, headers, calc_id, payload):
    return requests.put(f"{server}calculations/{calc_id}", json=payload, headers=headers)

def _delete(server, headers, calc_id):
    return requests.delete(f"{server}calculations/{calc_id}", headers=headers)


# ---------------------------------------------------------------------------
# Browse / Add
# ---------------------------------------------------------------------------
class TestBrowseAndAdd:
    def test_create_addition(self, fastapi_server, auth_headers):
        resp = _post(fastapi_server, auth_headers, {"type": "addition", "inputs": [1, 2, 3]})
        assert resp.status_code == 201
        data = resp.json()
        assert data["result"] == 6
        assert data["type"] == "addition"

    def test_create_subtraction(self, fastapi_server, auth_headers):
        resp = _post(fastapi_server, auth_headers, {"type": "subtraction", "inputs": [10, 3]})
        assert resp.status_code == 201
        assert resp.json()["result"] == 7

    def test_create_multiplication(self, fastapi_server, auth_headers):
        resp = _post(fastapi_server, auth_headers, {"type": "multiplication", "inputs": [2, 3, 4]})
        assert resp.status_code == 201
        assert resp.json()["result"] == 24

    def test_create_division(self, fastapi_server, auth_headers):
        resp = _post(fastapi_server, auth_headers, {"type": "division", "inputs": [100, 4]})
        assert resp.status_code == 201
        assert resp.json()["result"] == 25

    def test_create_division_by_zero_returns_400(self, fastapi_server, auth_headers):
        resp = _post(fastapi_server, auth_headers, {"type": "division", "inputs": [10, 0]})
        assert resp.status_code == 400

    def test_create_invalid_type_returns_400(self, fastapi_server, auth_headers):
        resp = _post(fastapi_server, auth_headers, {"type": "modulus", "inputs": [10, 3]})
        assert resp.status_code == 400

    def test_list_contains_created_calculation(self, fastapi_server, auth_headers):
        _post(fastapi_server, auth_headers, {"type": "addition", "inputs": [5, 5]})
        resp = _list(fastapi_server, auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_list_requires_auth(self, fastapi_server):
        resp = _list(fastapi_server, {})
        assert resp.status_code == 401

    def test_create_requires_auth(self, fastapi_server):
        resp = _post(fastapi_server, {}, {"type": "addition", "inputs": [1, 2]})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
class TestRead:
    def test_get_by_id(self, fastapi_server, auth_headers):
        created = _post(fastapi_server, auth_headers, {"type": "addition", "inputs": [7, 3]}).json()
        resp = _get(fastapi_server, auth_headers, created["id"])
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]
        assert resp.json()["result"] == 10

    def test_get_nonexistent_returns_404(self, fastapi_server, auth_headers):
        resp = _get(fastapi_server, auth_headers, "00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_get_invalid_uuid_returns_400(self, fastapi_server, auth_headers):
        resp = _get(fastapi_server, auth_headers, "not-a-uuid")
        assert resp.status_code == 400

    def test_get_requires_auth(self, fastapi_server, auth_headers):
        created = _post(fastapi_server, auth_headers, {"type": "addition", "inputs": [1, 1]}).json()
        resp = _get(fastapi_server, {}, created["id"])
        assert resp.status_code == 401

    def test_cannot_read_other_users_calculation(self, fastapi_server, auth_headers):
        """Calculation created by user A is not visible to user B."""
        from faker import Faker
        fake = Faker()
        # Register a second user
        u2 = {
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.unique.email(),
            "username": fake.unique.user_name(),
            "password": "AnotherPass1!",
            "confirm_password": "AnotherPass1!",
        }
        requests.post(f"{fastapi_server}auth/register", json=u2)
        login2 = requests.post(f"{fastapi_server}auth/login", json={
            "username": u2["username"], "password": u2["password"]
        }).json()
        headers2 = {"Authorization": f"Bearer {login2['access_token']}"}

        created = _post(fastapi_server, auth_headers, {"type": "addition", "inputs": [1, 2]}).json()
        resp = _get(fastapi_server, headers2, created["id"])
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------
class TestEdit:
    def test_update_inputs_recalculates_result(self, fastapi_server, auth_headers):
        created = _post(fastapi_server, auth_headers, {"type": "addition", "inputs": [1, 2]}).json()
        resp = _put(fastapi_server, auth_headers, created["id"], {"inputs": [10, 20, 30]})
        assert resp.status_code == 200
        assert resp.json()["result"] == 60

    def test_update_nonexistent_returns_404(self, fastapi_server, auth_headers):
        resp = _put(fastapi_server, auth_headers, "00000000-0000-0000-0000-000000000000", {"inputs": [1, 2]})
        assert resp.status_code == 404

    def test_update_requires_auth(self, fastapi_server, auth_headers):
        created = _post(fastapi_server, auth_headers, {"type": "addition", "inputs": [1, 2]}).json()
        resp = _put(fastapi_server, {}, created["id"], {"inputs": [5, 5]})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
class TestDelete:
    def test_delete_removes_calculation(self, fastapi_server, auth_headers):
        created = _post(fastapi_server, auth_headers, {"type": "addition", "inputs": [1, 1]}).json()
        del_resp = _delete(fastapi_server, auth_headers, created["id"])
        assert del_resp.status_code == 204
        get_resp = _get(fastapi_server, auth_headers, created["id"])
        assert get_resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, fastapi_server, auth_headers):
        resp = _delete(fastapi_server, auth_headers, "00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_delete_requires_auth(self, fastapi_server, auth_headers):
        created = _post(fastapi_server, auth_headers, {"type": "addition", "inputs": [1, 2]}).json()
        resp = _delete(fastapi_server, {}, created["id"])
        assert resp.status_code == 401
