# Caffeine Tracker Integration

## Build & Test
- **Install**: `task install` (uses `uv`)
- **Test**: `task test` (runs all 43 tests)
- **Lint/Format**: `task lint`, `task format`
- **Deploy**: `task deploy` (rsync to HA)
- **Reload**: `task reload` (HA API call)
- **Restart**: `task restart` (Full HA restart via API)

## Architecture
- **`coordinator.py`**: Heart of the integration. Pure computation functions for decay/absorption logic + HA DataUpdateCoordinator.
- **`__init__.py`**: Entry point. Domain-level service registrations occur here in `async_setup`.
- **`sensor.py`**: Entity definitions. `CaffeineCurrentSensor` is the primary entity.
- **`const.py`**: Constants, domain, and default settings.
- **`services.yaml`**: UI definitions for services.

## Service Handling
- Services are registered at the **domain level**.
- They use `service.async_extract_config_entry_ids(call)` (non-deprecated) to ensure a single call per target device/profile.
- Supported services: `log_consumption`, `remove_last_consumption`, `remove_consumption`, `clear_today`.
- **Targeting**: Target the **Device** for reliable once-per-profile logging.

## Testing
- Tests are in `tests/`.
- `test_sensor.py` covers integration tests, service calls, and device targeting.
- `test_coordinator.py` covers pure logic and computation.
- Use `uv run pytest` to execute.

## Commit conventions
Always use [Conventional Commits](https://www.conventionalcommits.org/). Commit type determines changelog inclusion and version bumps.

| Prefix | Use for | In changelog |
|--------|---------|--------------|
| `feat:` | New user-facing feature | Yes — Features |
| `fix:` | Bug fix | Yes — Bug Fixes |
| `docs:` | Documentation only | Yes — Documentation |
| `perf:` | Performance improvement | Yes — Performance |
| `refactor:` | Internal refactor, no behaviour change | Yes — Refactoring |
| `test:` | Adding or updating tests | Yes — Testing |
| `chore(deps):` | Dependency updates | Yes — Dependencies |
| `chore:` | Maintenance, tooling, config | No |
| `ci:` | CI/CD pipeline changes | No |

Use `feat!:` or a `BREAKING CHANGE:` footer for breaking changes. Never use generic messages like "update", "fix stuff", or "WIP".
