
.PHONY: install setup-server run-server run-client test clean

install:
	bash install.sh

setup-server:
	cp .env.example .env
	docker-compose build

run-server:
	docker-compose up

run-client:
	python3 client/app.py

test:
	pytest server/tests
	pytest client/tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache
