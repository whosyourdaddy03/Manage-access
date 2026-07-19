PYTHON ?= python3
API_VENV := api/.venv

.PHONY: api-install api-run api-test web-install web-run web-build compose-up ros-build

api-install:
	$(PYTHON) -m venv $(API_VENV)
	$(API_VENV)/bin/pip install -e "./api[dev]"

api-run:
	cd api && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

api-test:
	cd api && .venv/bin/python -m pytest

web-install:
	cd web && npm install

web-run:
	cd web && npm run dev

web-build:
	cd web && npm run build

compose-up:
	docker compose up --build

ros-build:
	cd ros2_ws && colcon build --symlink-install
