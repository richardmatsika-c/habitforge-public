# tests/test_api.py

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session
from app.main import app
from app.db import engine  # <-- reuse the app's engine
from app.db import get_session

# Import ALL your models to ensure they're registered with SQLModel
from app.models import User, Habit
from app.security import get_password_hash

# --- 1. Test Database Setup ---
# NOTE: we reuse `engine` from app.db so the app and tests share the same DB/connection.


# --- 2. Test Session Fixture ---
@pytest.fixture(name="session")
def session_fixture():
    # Ensure models are registered
    from app.models import User, Habit

    # Create all tables on the app engine (the same engine the app uses)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    # Clean up after test run
    SQLModel.metadata.drop_all(engine)


# --- 3. Test Client Fixture ---
@pytest.fixture(name="client")
def client_fixture(session: Session):
    # Override the dependency to use our test session
    def get_session_override():
        return session

    # Override the get_session dependency
    app.dependency_overrides[get_session] = get_session_override

    # Create test client
    client = TestClient(app)
    yield client

    # Clean up
    app.dependency_overrides.clear()


# --- Helper function to create test user ---
def create_test_user(session: Session):
    """Helper to create a test user directly in the database"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_test_habit(session: Session, user_id: int):
    """Helper to create a test habit directly in the database"""
    habit = Habit(name="Test Habit", frequency="daily", user_id=user_id)
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return habit


# --- API Tests ---


def test_register_user(client: TestClient, session: Session):
    """Test registering a new user on a clean database."""
    response = client.post(
        "/auth/register",
        json={
            "username": "newuser",  # Use a different username to avoid conflicts
            "password": "password123",
            "email": "newuser@example.com",
        },
    )
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["username"] == "newuser"
    assert "id" in data


def test_register_existing_user(client: TestClient, session: Session):
    """Test that registering a user who already exists fails."""
    # Create user directly in database first
    create_test_user(session)

    # Try to create same user via API
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "password": "password123",
            "email": "test@example.com",
        },
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_login(client: TestClient, session: Session):
    """Test logging in with a valid user."""
    # Create user directly in database
    create_test_user(session)

    # Login via API
    response = client.post(
        "/auth/token", data={"username": "testuser", "password": "password123"}
    )
    assert response.status_code == 200, response.json()
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient, session: Session):
    """Test that logging in with a bad password fails."""
    # Create user directly in database
    create_test_user(session)

    # Try to login with wrong password
    response = client.post(
        "/auth/token", data={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_create_and_get_habits(client: TestClient, session: Session):
    """Test creating and getting habits using a valid token."""
    # Create user directly in database
    user = create_test_user(session)

    # Login to get token
    login_response = client.post(
        "/auth/token", data={"username": "testuser", "password": "password123"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a habit via API
    create_response = client.post(
        "/habits/", headers=headers, json={"name": "Read a book", "frequency": "daily"}
    )
    assert create_response.status_code == 200, create_response.json()
    data = create_response.json()
    assert data["name"] == "Read a book"
    assert data["user_id"] == user.id

    # Get habits via API
    get_response = client.get("/habits/", headers=headers)
    assert get_response.status_code == 200, get_response.json()
    data_list = get_response.json()
    assert isinstance(data_list, list)
    assert len(data_list) == 1
    assert data_list[0]["name"] == "Read a book"


def test_protected_route_without_token(client: TestClient):
    """Test that protected routes require authentication."""
    response = client.get("/protected")
    assert response.status_code == 401
    assert "detail" in response.json()


def test_protected_route_with_valid_token(client: TestClient, session: Session):
    """Test accessing a protected route with a valid token."""
    # Create user directly in database
    create_test_user(session)

    # Login to get token
    login_response = client.post(
        "/auth/token", data={"username": "testuser", "password": "password123"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Access protected route
    response = client.get("/protected", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


def test_health_check(client: TestClient):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_root_endpoint(client: TestClient):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["status"] == "healthy"
