.PHONY: build run-backend run-frontend run-tests test

BACKEND_PORT ?= 8001
BACKEND_HOST ?= 127.0.0.1
FRONTEND_PORT ?= 3000

build:
	npm --prefix frontend run build

run-backend:
	python -m uvicorn app.main:app --host $(BACKEND_HOST) --port $(BACKEND_PORT)

run-frontend:
	npm --prefix frontend run dev -- --port $(FRONTEND_PORT)

run-tests: test

test:
	python -m pytest -q
