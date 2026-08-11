SHELL := /bin/sh

.PHONY: dev down install test lint typecheck e2e migrate seed evaluate release-check clean

dev:
	@sh scripts/compose.sh up --build

down:
	@sh scripts/compose.sh down

install:
	@python3 -m venv apps/api/.venv
	@apps/api/.venv/bin/python -m pip install --upgrade pip
	@apps/api/.venv/bin/python -m pip install -e 'apps/api[dev]'
	@cd apps/web && npm install

test:
	@apps/api/.venv/bin/pytest apps/api/tests
	@cd apps/web && npm test -- --run

lint:
	@apps/api/.venv/bin/ruff check apps/api
	@cd apps/web && npm run lint

typecheck:
	@apps/api/.venv/bin/mypy apps/api/src
	@cd apps/web && npm run typecheck

e2e:
	@cd apps/web && npm run e2e

migrate:
	@cd apps/api && .venv/bin/alembic upgrade head

seed:
	@cd apps/api && .venv/bin/research-lab ingest-openalex --target 600

evaluate:
	@cd apps/api && .venv/bin/research-lab evaluate

release-check:
	@sh scripts/public-release-check.sh

clean:
	@rm -rf apps/api/.pytest_cache apps/api/.mypy_cache apps/api/.ruff_cache
	@rm -rf apps/api/src/*.egg-info
	@rm -rf apps/web/.next apps/web/coverage apps/web/playwright-report apps/web/test-results

