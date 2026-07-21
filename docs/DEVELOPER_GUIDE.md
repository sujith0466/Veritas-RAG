# Developer Guide

## Project Structure

```
raguard/
+-- backend/
|   +-- api/v1/           # FastAPI routers
|   +-- core/             # Cross-cutting concerns
|   +-- modules/          # Domain modules
|   +-- configs/          # Settings classes
+-- alembic/              # Database migrations
+-- tests/
|   +-- unit/
|   +-- integration/
|   +-- benchmarks/
|   +-- chaos/
+-- docs/                 # Documentation
+-- archive/              # Engineering history
+-- docker-compose.yml
+-- Dockerfile
```

## Development Setup

```bash
git clone https://github.com/your-org/raguard.git
cd raguard
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn backend.main:app --reload
```

## Running Tests

```bash
# All tests
pytest tests/

# Unit tests only
pytest tests/unit/

# With coverage
pytest tests/ --cov=backend --cov-report=html
```

## Adding a New Module

1. Create `backend/modules/<name>/` with subdirs: `api/`, `schemas/`, `services/`, `repositories/`.
2. Define Pydantic DTOs in `schemas/<name>_dto.py`.
3. Implement service in `services/<name>_service.py`.
4. Register router in `backend/api/v1/router.py`.
5. Write unit tests in `tests/unit/backend/modules/<name>/`.

## Code Standards

- Format: Black (line length 100)
- Linting: Ruff
- Type hints: Required on all public methods
- Docstrings: Required on all service methods
