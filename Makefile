.PHONY: up down logs migrate seed test test-opa opa-test opa-fmt lint fmt worker api

up:
	docker compose up --build -d

down:
	docker compose down -v

logs:
	docker compose logs -f api worker

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(m)"

seed:
	python scripts/seed.py

api:
	uvicorn app.main:app --reload

worker:
	celery -A app.workers.celery_app.celery_app worker -Q aigov -l info

test:
	pytest -q

# Rego unit tests (requires the opa binary on PATH).
opa-test:
	opa test policies/ -v

opa-fmt:
	opa fmt --write policies/

# Python tests including the live-OPA suite; needs a server on :8181.
test-opa:
	opa run --server --addr localhost:8181 policies/ & \
	sleep 2 && pytest -q; kill %1

lint:
	ruff check app tests && mypy app

fmt:
	ruff check --fix app tests && ruff format app tests
