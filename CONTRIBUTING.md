# Contributing to RAGuard AI

Thank you for your interest in contributing!

## Development Workflow

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Write code following the project's style guide.
4. Add tests to `tests/unit/` and `tests/integration/`.
5. Ensure all tests pass: `pytest tests/`.
6. Run linting: `ruff check backend/`.
7. Submit a Pull Request against `main`.

## Code Standards

- All new code must include type hints.
- All public methods require docstrings.
- Minimum test coverage: 80% for new modules.
- No hardcoded secrets or API keys.

## Architecture Rules

- DO NOT add business logic to API routers.
- DO NOT bypass the repository layer for database access.
- DO NOT introduce new LLM calls outside the Generation module.
- DO follow the established module pattern: `api/` + `schemas/` + `services/` + `repositories/`.

## Pull Request Checklist

- [ ] Tests added and passing.
- [ ] Linting clean.
- [ ] Documentation updated.
- [ ] No breaking changes.
- [ ] CHANGELOG.md updated.
