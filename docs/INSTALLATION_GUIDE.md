# Installation Guide

## Prerequisites

| Requirement | Minimum Version |
|-------------|----------------|
| Python | 3.13+ |
| PostgreSQL | 15+ |
| Redis | 7+ |
| Qdrant | 1.7+ |
| Docker | 24+ (optional) |
| Docker Compose | 2.20+ (optional) |

## Option A — Docker (Recommended)

```bash
git clone https://github.com/your-org/raguard.git
cd raguard
cp .env.example .env
# Edit .env with your secrets
docker-compose up -d
```

Services start on:
- API: http://localhost:8000
- Qdrant: http://localhost:6333
- Postgres: localhost:5432
- Redis: localhost:6379

## Option B — Local Development

```bash
git clone https://github.com/your-org/raguard.git
cd raguard

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the application
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## Verify Installation

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```
