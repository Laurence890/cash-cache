import pytest
from unittest.mock import patch, MagicMock
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


# Test 1: Successful login
@patch("app.get_supabase")
def test_valid_login(mock_supabase, client):

    mock_response = MagicMock()
    mock_response.username = "test-user-123"
    mock_response.user.email = "cash@example.com"

    mock_supabase.return_value.auth.sign_in_with_password.return_value = (
        mock_response
    )

    response = client.post("/login", data={
        "username_or_email": "cash@example.com",
        "password": "testpassword123"
    })

    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    with client.session_transaction() as session:
        assert session["logged_in"] is True
        assert session["username"] == "test-user-123"
        assert session["email"] == "cash@example.com"

    mock_supabase.return_value.auth.sign_in_with_password.assert_called_once_with({
        "email": "cash@example.com",
        "password": "testpassword123"
    })


# Test 2: Invalid login
@patch("app.get_supabase")
def test_invalid_login(mock_supabase, client):

    mock_supabase.return_value.auth.sign_in_with_password.side_effect = (
        Exception("Invalid login credentials")
    )

    response = client.post("/login", data={
        "username_or_email": "cash@example.com",
        "password": "wrongpassword"
    })

    assert response.status_code == 200
    assert b"An error occurred during login. Please try again." in response.data

    with client.session_transaction() as session:
        assert not session.get("logged_in")


# Test 3: Empty credentials
@patch("app.get_supabase")
def test_empty_login(mock_supabase, client):

    response = client.post("/login", data={
        "username_or_email": "",
        "password": ""
    })

    assert response.status_code == 200
    assert b"Please fill out all fields." in response.data

    mock_supabase.assert_not_called()


# Test 4: Unauthorized dashboard access
def test_unauthorized_access(client):

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


# Test 5: Logout
def test_logout(client):

    with client.session_transaction() as session:
        session["logged_in"] = True
        session["user_id"] = "test-user-123"

    response = client.get("/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"

    with client.session_transaction() as session:
        assert not session.get("logged_in")
        assert "user_id" not in session