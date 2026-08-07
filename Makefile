# ==============================================================================
# RAGuard AI — Master Developer Makefile
# ==============================================================================
# One-command interface for onboarding, orchestration, migrations, and quality gates.
# Works across Linux, macOS, WSL, and Git Bash.
# For native Windows PowerShell, run the scripts in ./infrastructure/scripts/*.ps1
# ==============================================================================

.PHONY: help setup start stop restart reset migrate health logs clean test lint build dev-tools

# Default target when simply typing 'make'
help:
	@echo "========================================================================"
	@echo "                   RAGuard AI — Developer Interface                     "
	@echo "========================================================================"
	@echo "  make setup       : One-command turnkey onboarding (build, start, migrate)"
	@echo "  make qa-bootstrap: Run idempotent QA account creation and data seeding"
	@echo "  make start       : Start all core services in background (docker compose up -d)"
	@echo "  make stop        : Stop all containers and clean bridge networks"
	@echo "  make restart     : Restart all containers"
	@echo "  make reset       : Clean teardown (-v) and fresh database re-initialization"
	@echo "  make migrate     : Execute Alembic database migrations inside backend"
	@echo "  make health      : Check 3-tier health probes across all containers"
	@echo "  make logs        : Stream multi-service logs (Ctrl+C to exit)"
	@echo "  make clean       : Prune dangling images, caches, and orphan volumes"
	@echo "  make dev-tools   : Start core services + pgAdmin (5050) & Redis Commander (8081)"
	@echo "========================================================================"

setup:
	@chmod +x ./infrastructure/scripts/*.sh
	@./infrastructure/scripts/bootstrap.sh

qa-bootstrap:
	@echo "========================================================================"
	@echo "          Bootstrapping QA Environment & Test Data                      "
	@echo "========================================================================"
	@docker compose exec api python -m backend.core.bootstrap_qa
	@docker compose exec api python -m backend.core.seed_enterprise_data
	@echo "✅ QA Bootstrap complete."

start:
	@docker compose up -d
	@echo "✅ RAGuard AI core services launched! UI at http://localhost:5173"

stop:
	@docker compose down
	@echo "🛑 RAGuard AI services stopped cleanly."

restart:
	@docker compose restart
	@echo "🔄 Services restarted."

reset:
	@./infrastructure/scripts/reset.sh

migrate:
	@docker compose exec backend alembic upgrade head
	@echo "✅ Database migrations applied successfully."

health:
	@./infrastructure/scripts/health.sh

logs:
	@docker compose logs -f --tail=100

clean:
	@./infrastructure/scripts/clean.sh

dev-tools:
	@docker compose --profile dev-tools up -d
	@echo "✅ Core + Dev Tools launched! pgAdmin: http://localhost:5050, Redis Commander: http://localhost:8081"

test:
	@docker compose exec backend pytest tests/ -v
	@echo "✅ Unit & verification tests executed."

lint:
	@docker compose exec backend ruff check backend/
	@docker compose exec backend mypy backend/
	@echo "✅ Code quality checks completed."
