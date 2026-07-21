# Developer Onboarding Checklist

Welcome to the RAGuard team! Complete these steps to set up your environment.

- [ ] Install Python 3.13, Docker, and Docker Compose.
- [ ] Clone the repository: `git clone https://github.com/your-org/raguard.git`
- [ ] Create a virtual environment: `python -m venv .venv && source .venv/bin/activate`
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Copy `.env.example` to `.env`.
- [ ] Start supporting infrastructure: `docker-compose up -d postgres redis qdrant`
- [ ] Run migrations: `alembic upgrade head`
- [ ] Run the test suite: `pytest tests/` (Ensure all pass).
- [ ] Run the API: `uvicorn backend.main:app --reload`
- [ ] Review `ARCHITECTURE_WALKTHROUGH.md` and `CODING_STANDARDS.md`.
