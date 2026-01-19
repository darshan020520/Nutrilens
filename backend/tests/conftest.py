"""
Pytest configuration and fixtures for testing.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base


@pytest.fixture(scope="function")
def test_db():
    """
    Create a test database for each test function.

    Returns:
        SQLAlchemy Session
    """
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def sample_user(test_db):
    """
    Create a sample user for testing.

    Args:
        test_db: Test database session

    Returns:
        User object
    """
    from app.models.database import User

    user = User(
        email="test@example.com",
        hashed_password="hashed_password_here",
        is_active=True,
        onboarding_completed=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    return user
