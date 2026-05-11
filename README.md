# IS601 Final Project — Calculations API

A full-stack web application built with **FastAPI** that lets authenticated users create, save, and manage mathematical calculations through a clean browser interface. The app pairs a RESTful JSON API with server-rendered Jinja2 templates styled with Tailwind CSS, backed by PostgreSQL, and secured with JWT authentication.

**Docker Hub:** [docsnoop/is601-final](https://hub.docker.com/repository/docker/docsnoop/is601-final/general)

---

## Overview

### What the application does

Users register for an account, log in, and land on a personal dashboard where they can perform calculations and browse their full history. Every calculation is persisted to the database and tied to the user who created it, so each user sees only their own data.

### Supported calculation types

| Operation | Description | Example |
|---|---|---|
| Addition | Sum of all inputs | `[10, 5, 3]` → `18` |
| Subtraction | First value minus each subsequent value | `[20, 5, 3]` → `12` |
| Multiplication | Product of all inputs | `[2, 3, 4]` → `24` |
| Division | First value divided by each subsequent value | `[100, 2, 5]` → `10` |

### Key features

**Authentication & security**
- Account registration with strong password requirements (uppercase, lowercase, digit, special character)
- JWT-based login returning a short-lived access token and a longer-lived refresh token, each signed with separate secrets
- bcrypt password hashing with a configurable work factor
- Token blacklisting via Redis so logout immediately invalidates the token

**Calculation management (BREAD)**
- **Browse** — dashboard table listing all of the user's calculations with type, inputs, result, and timestamp
- **Read** — dedicated view page for a single calculation
- **Edit** — update the inputs of an existing calculation; the result is recomputed automatically
- **Add** — form to create a new calculation; result is computed server-side on save
- **Delete** — remove a calculation with a confirmation prompt

**User profile**
- View and update profile information (username, email, first name, last name)
- Change password with current-password verification and strength enforcement
- All profile changes are validated both client-side (real-time) and server-side

**Developer experience**
- Interactive API documentation at `/docs` (Swagger UI) and `/redoc`
- Full test suite: unit, integration, and E2E (Playwright) layers
- CI/CD pipeline via GitHub Actions — tests → Docker build → push to Docker Hub
- One-command local setup with Docker Compose (app + PostgreSQL + pgAdmin)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Running the Application](#running-the-application)
   - [With Docker Compose (recommended)](#with-docker-compose-recommended)
   - [Without Docker (local)](#without-docker-local)
3. [Running Tests](#running-tests)
   - [Inside Docker](#inside-docker)
   - [Locally (without Docker)](#locally-without-docker)
   - [Test categories](#test-categories)
4. [Database Migrations (Alembic)](#database-migrations-alembic)
5. [Environment Variables](#environment-variables)
6. [Project Structure](#project-structure)
7. [Docker Hub](#docker-hub)
8. [Git & SSH Setup](#git--ssh-setup)

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Docker Desktop | 24+ | Required for the Docker path |
| Docker Compose | v2 (included with Docker Desktop) | |
| Python | 3.10+ | Required for the local path |
| Git | any | |

---

## Running the Application

### With Docker Compose (recommended)

Docker Compose starts the FastAPI app, a PostgreSQL 17 database, and pgAdmin together with a single command — no local Python installation needed.

**1. Clone the repository**

```bash
git clone <repository-url>
cd <repository-directory>
```

**2. Start all services**

```bash
docker compose up --build
```

The first run builds the image. Subsequent runs skip the build step:

```bash
docker compose up
```

**3. Open the app**

| Service | URL |
|---|---|
| Web UI / API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| pgAdmin | http://localhost:5050 |

pgAdmin credentials: set via `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD` in your `.env` file

**4. Stop the services**

```bash
docker compose down
```

To also delete the database volume (full reset):

```bash
docker compose down -v
```

---

### Without Docker (local)

Use this path if you want to run the app directly on your machine.

**1. Install Python 3.10+**

- macOS: `brew install python`
- Windows: [python.org/downloads](https://www.python.org/downloads/) — check **Add Python to PATH** during setup

**2. Create and activate a virtual environment**

```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate.bat
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Start a PostgreSQL database**

The app requires a running PostgreSQL instance. The easiest option is to spin up just the database container:

```bash
docker compose up db -d
```

Or install PostgreSQL locally and create the databases:

```sql
CREATE DATABASE fastapi_db;
CREATE DATABASE fastapi_test_db;
```

**5. Configure environment variables**

Copy the provided template and fill in your own values:

```bash
cp .env.example .env
```

Then edit `.env` — at minimum set these:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-db-password>
POSTGRES_DB=fastapi_db
DATABASE_URL=postgresql://postgres:<your-db-password>@localhost:5432/fastapi_db
JWT_SECRET_KEY=<your-random-secret-min-32-chars>
JWT_REFRESH_SECRET_KEY=<your-random-secret-min-32-chars>
PGADMIN_DEFAULT_EMAIL=<your-pgadmin-email>
PGADMIN_DEFAULT_PASSWORD=<your-pgadmin-password>
```

Generate strong secrets with:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**6. Run the server**

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The app is available at http://localhost:8000.

---

## Running Tests

The test suite uses **pytest** with coverage reporting. It contains three layers:

| Layer | Location | What it tests |
|---|---|---|
| Unit | `tests/unit/` | Schema validation, model methods, pure logic |
| Integration | `tests/integration/` | API routes, database interactions |
| E2E | `tests/e2e/` | Full browser flows via Playwright |

### Inside Docker

Run the full test suite inside the running web container:

```bash
# Start services first (if not already running)
docker compose up -d

# Run all tests
docker compose exec web pytest

# Run only unit tests
docker compose exec web pytest tests/unit/

# Run only integration tests
docker compose exec web pytest tests/integration/

# Run only E2E tests
docker compose exec web pytest tests/e2e/

# Run a specific test file
docker compose exec web pytest tests/unit/test_profile.py -v
```

### Locally (without Docker)

Ensure the database is running and environment variables are set (see [Without Docker](#without-docker-local) above), then:

**1. Install Playwright browsers (required for E2E tests)**

```bash
playwright install chromium
```

**2. Run the full test suite**

```bash
pytest
```

**3. Common options**

```bash
# Verbose output
pytest -v

# Run only unit tests (no server needed)
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run only E2E tests
pytest tests/e2e/

# Run a specific test file
pytest tests/integration/test_profile.py -v

# Run tests matching a keyword
pytest -k "password"

# Skip slow tests (default behaviour — slow tests are skipped unless opted in)
pytest

# Include slow tests
pytest --run-slow

# Keep the test database after the run for inspection
pytest --preserve-db
```

**4. Coverage report**

Coverage is collected automatically. After any `pytest` run:

- Terminal: printed inline with missing lines highlighted
- HTML: open `htmlcov/index.html` in a browser for a line-by-line view

```bash
open htmlcov/index.html   # macOS
start htmlcov/index.html  # Windows
```

### Test categories

Tests are tagged with markers defined in `pytest.ini`:

| Marker | Description | Run with |
|---|---|---|
| `slow` | Long-running tests (bulk ops, etc.) | `pytest --run-slow` |
| `fast` | Quick unit-level tests | `pytest -m fast` |
| `e2e` | Full browser automation tests | `pytest -m e2e` |

---

## Database Migrations (Alembic)

### Current approach

The application uses `Base.metadata.create_all()` at startup to create all tables automatically. No migration tool is configured by default.

### When migrations are required

Switch to Alembic whenever you need to make schema changes to an existing database without losing data — for example, adding a column, renaming a field, or changing a constraint. Running `create_all` again on an existing database **does not** apply changes to tables that already exist.

### One-time setup

**1. Install Alembic**

Add it to `requirements.txt` and install:

```bash
pip install alembic
```

**2. Initialise Alembic in the project root**

```bash
alembic init migrations
```

This creates:
```
migrations/
├── env.py
├── script.py.mako
└── versions/
alembic.ini
```

**3. Point Alembic at the application database and models**

Edit `alembic.ini` — remove the hardcoded URL so it is read from the environment at runtime:

```ini
sqlalchemy.url =
```

Edit `migrations/env.py` — import the app's `Base` and read `DATABASE_URL` from settings:

```python
from app.database import Base
from app.core.config import settings

# Replace the existing `target_metadata = None` line with:
target_metadata = Base.metadata

# Replace the existing `run_migrations_offline()` config.get_main_option call with:
url = settings.DATABASE_URL
```

Full `run_migrations_online` block after the change:

```python
def run_migrations_online() -> None:
    from sqlalchemy import create_engine
    connectable = create_engine(settings.DATABASE_URL)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

### Creating a migration

After changing a SQLAlchemy model, generate a new migration script:

```bash
# Auto-generate based on model diff
alembic revision --autogenerate -m "describe your change"

# Or create a blank script to write manually
alembic revision -m "describe your change"
```

The new file appears in `migrations/versions/`. Review it before applying.

### Applying migrations

```bash
# Apply all pending migrations (upgrade to latest)
alembic upgrade head

# Apply a specific number of steps
alembic upgrade +1

# Roll back one migration
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade <revision-id>
```

### Checking migration status

```bash
# Show current revision applied to the database
alembic current

# Show full migration history
alembic history --verbose
```

### Running migrations with Docker

```bash
# Apply migrations inside the running web container
docker compose exec web alembic upgrade head

# Or as a one-off container (useful in CI/CD)
docker compose run --rm web alembic upgrade head
```

### Running migrations in CI/CD

Add an upgrade step to the GitHub Actions workflow **before** starting the application, after the database service is healthy:

```yaml
- name: Apply database migrations
  env:
    DATABASE_URL: postgresql://postgres:postgres@localhost:5432/fastapi_db
  run: alembic upgrade head
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | *(required)* | PostgreSQL connection string — never commit credentials |
| `JWT_SECRET_KEY` | *(required)* | Secret for signing access tokens |
| `JWT_REFRESH_SECRET_KEY` | *(required)* | Secret for signing refresh tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `BCRYPT_ROUNDS` | `12` | bcrypt work factor for password hashing |
| `REDIS_URL` | *(optional)* | Redis URL for token blacklisting on logout |

---

## Project Structure

```
.
├── app/
│   ├── auth/           # JWT helpers, dependencies, Redis blacklist
│   ├── core/           # Settings (Pydantic BaseSettings)
│   ├── models/         # SQLAlchemy models (User, Calculation)
│   ├── operations/     # Calculation logic (add, subtract, multiply, divide)
│   ├── schemas/        # Pydantic request/response schemas
│   ├── database.py     # Engine, session factory, Base
│   ├── database_init.py
│   └── main.py         # FastAPI app, all routes
├── templates/          # Jinja2 HTML templates
├── static/             # CSS, JS, images
├── tests/
│   ├── unit/           # Schema and model logic tests
│   ├── integration/    # API route + DB tests
│   └── e2e/            # Playwright browser tests
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
└── requirements.txt
```

---

## Git & SSH Setup

### Install Git

- macOS: `brew install git`
- Windows: [git-scm.com/download/win](https://git-scm.com/download/win)

```bash
git --version   # verify
```

### Configure Git globals

```bash
git config --global user.name "Your Name"
git config --global user.email "your_email@example.com"
```

### Generate SSH key and connect to GitHub

```bash
# Generate key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Start the agent and add the key
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# Copy the public key
cat ~/.ssh/id_ed25519.pub   # then paste it into github.com/settings/keys

# Test the connection
ssh -T git@github.com
```

### Clone the repository

```bash
git clone <repository-url>
cd <repository-directory>
```

---

## Docker Hub

The production image is published automatically on every push to `main`/`master` via GitHub Actions.

| Resource | Link |
|---|---|
| Repository | [docsnoop/is601-final](https://hub.docker.com/repository/docker/docsnoop/is601-final/general) |
| Latest tag | `docsnoop/is601-final:latest` |

**Pull the latest image:**

```bash
docker pull docsnoop/is601-final:latest
```

---

## Quick Reference

| Task | Command |
|---|---|
| Start app (Docker) | `docker compose up --build` |
| Stop app (Docker) | `docker compose down` |
| Run all tests (Docker) | `docker compose exec web pytest` |
| Run all tests (local) | `pytest` |
| Unit tests only | `pytest tests/unit/` |
| Integration tests only | `pytest tests/integration/` |
| E2E tests only | `pytest tests/e2e/` |
| Include slow tests | `pytest --run-slow` |
| View coverage report | `open htmlcov/index.html` |
| API docs | http://localhost:8000/docs |
