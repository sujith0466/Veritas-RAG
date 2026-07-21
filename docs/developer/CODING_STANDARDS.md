# Coding Standards

RAGuard AI adheres to strict engineering guidelines to maintain enterprise reliability.

## 1. Type Hinting
- Every function signature **must** include type hints for parameters and return types.
- Example: `async def extract_intent(query: str) -> IntentDTO:`

## 2. Docstrings
- Every public module, class, and method requires a docstring describing its purpose, parameters, and exceptions raised.

## 3. Asynchronous Execution
- No blocking I/O calls are permitted in the event loop.
- Use `httpx.AsyncClient` instead of `requests`.
- Use `asyncpg` via SQLAlchemy's `AsyncSession` for database queries.

## 4. Error Handling
- Do not return generic `500` errors.
- Catch specific exceptions and raise a subclass of `RAGuardException` containing a standardized `error_code` (e.g., `DB_001`).

## 5. Testing
- Every module must have >90% unit test coverage.
- Use `pytest-asyncio` for async tests.
