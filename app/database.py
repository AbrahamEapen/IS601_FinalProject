"""
Database Configuration and Session Management

This module sets up the SQLAlchemy engine, session factory, and declarative
base used throughout the application.  It also exposes factory functions
(get_engine, get_sessionmaker) so the test suite can create isolated
sessions pointed at the test database without modifying module-level state.

Key objects exported:
  engine          : Default SQLAlchemy engine connected to DATABASE_URL.
  SessionLocal    : Default session factory bound to `engine`.
  Base            : Declarative base class; all ORM models inherit from this.
  get_db()        : FastAPI dependency that yields a per-request DB session.
  get_engine()    : Factory for creating an engine from an arbitrary URL.
  get_sessionmaker(): Factory for creating a sessionmaker bound to any engine.

Connection string:
  Read from settings.DATABASE_URL, which is sourced from the DATABASE_URL
  environment variable (or .env file).  Format:
    postgresql://<user>:<password>@<host>:<port>/<dbname>

Session lifecycle:
  Each HTTP request gets its own session via the get_db() generator.
  The session is always closed in the finally block, even if the route
  handler raises an exception, preventing connection leaks.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# ---------------------------------------------------------------------------
# Default engine and session factory
# ---------------------------------------------------------------------------

# The database URL is read from application settings (env var DATABASE_URL).
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Create the SQLAlchemy engine.
# - autocommit=False : transactions must be committed explicitly; this is
#   the safe default that gives routes control over when data is persisted.
# - autoflush=False  : the session won't flush pending changes to the DB
#   automatically before queries, avoiding unexpected SQL at query time.
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base — all SQLAlchemy ORM models (User, Calculation, …) must
# inherit from this class so that Base.metadata.create_all() can discover them.
Base = declarative_base()


# ---------------------------------------------------------------------------
# FastAPI dependency — per-request database session
# ---------------------------------------------------------------------------

def get_db():
    """
    FastAPI dependency that provides a database session for a single request.

    Usage in a route:
        @app.get("/example")
        def example(db: Session = Depends(get_db)):
            return db.query(MyModel).all()

    The generator pattern (yield) allows FastAPI to run cleanup code after the
    route handler returns:
      - On success  : the session is simply closed (caller must commit).
      - On exception: the session is still closed, rolling back any uncommitted
                      changes automatically (SQLAlchemy's default behaviour).

    Yields:
        Session: An active SQLAlchemy ORM session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        # Always close the session to return the connection to the pool,
        # regardless of whether the request succeeded or raised an exception.
        db.close()


# ---------------------------------------------------------------------------
# Factory functions (used by the test suite)
# ---------------------------------------------------------------------------

def get_engine(database_url: str = SQLALCHEMY_DATABASE_URL):
    """
    Create and return a new SQLAlchemy engine for the given database URL.

    This factory is used by the test suite to create an engine pointed at
    the test database (fastapi_test_db) without overwriting the module-level
    `engine` that the production app uses.

    Args:
        database_url: A SQLAlchemy connection string.  Defaults to the
                      application's DATABASE_URL setting.

    Returns:
        A new Engine instance.
    """
    return create_engine(database_url)


def get_sessionmaker(engine):
    """
    Create and return a sessionmaker bound to the given engine.

    Paired with get_engine() so the test suite can build an isolated
    session factory:

        test_engine = get_engine(database_url=TEST_DATABASE_URL)
        TestingSessionLocal = get_sessionmaker(engine=test_engine)

    Args:
        engine: The SQLAlchemy Engine to bind the sessions to.

    Returns:
        A sessionmaker factory configured with autocommit=False and
        autoflush=False (matching the production defaults).
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
