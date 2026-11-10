.PHONY: install test lint format sample serve docker-build docker-run

install:
	pip install -e ".[dev,ml,llm]"

test:
	TC_EMBEDDING_BACKEND=tfidf pytest -q

lint:
	ruff check . && ruff format --check .

format:
	ruff check --fix . && ruff format .

sample:
	ticketsorter run -i data/sample_tickets.csv -o out

serve:
	ticketsorter serve --port 8000

docker-build:
	docker build -t ticket-categorizer .

docker-run:
	docker run --rm -p 8000:8000 --env-file .env ticket-categorizer
