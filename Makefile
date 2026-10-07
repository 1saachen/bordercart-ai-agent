.PHONY: test backend frontend

test:
	.venv/Scripts/python.exe -m pytest -q --tb=short

backend:
	.venv/Scripts/python.exe -m uvicorn app.presentation.server:app --host 127.0.0.1 --port 8000 --workers 1

frontend:
	npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
