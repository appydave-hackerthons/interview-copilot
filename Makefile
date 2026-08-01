.PHONY: install dev backend frontend build start test check

install:
	uv sync --dev
	cd frontend && npm install

backend:
	uv run uvicorn interview_copilot.app:app --reload --port 8787

frontend:
	cd frontend && npm run dev

dev:
	@trap 'kill 0' INT TERM EXIT; \
	uv run uvicorn interview_copilot.app:app --reload --port 8787 & \
	cd frontend && npm run dev

build:
	cd frontend && npm run build

start:
	uv run uvicorn interview_copilot.app:app --host 127.0.0.1 --port 8787

test:
	uv run pytest -q
	cd frontend && npm test

check: test build
