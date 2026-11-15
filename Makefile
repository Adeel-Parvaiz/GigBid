.PHONY: install test lint demo eval dev seed
dev:
	docker compose -f infra/docker-compose.yml --env-file .env up --build
seed:
	@echo 'sample data ships in data/sample; GigSim seeding comes from the instructor kit'
install:
	python -m pip install -e ".[dev]"
test:
	pytest -q
lint:
	ruff check .
demo:
	python -m scripts.demo
eval:
	python -m evals.runners.rag_eval && python -m evals.runners.decision_eval && python -m evals.runners.injection_eval && python -m evals.runners.ablation
