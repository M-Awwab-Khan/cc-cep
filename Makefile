.PHONY: test lint install-tools render deploy
test:
	uv run pytest -q
lint:
	uv run ruff check src tests scripts
install-tools:
	python3 scripts/install_tools.py
render:
	uv run python scripts/render_deploy.py
	uv run python scripts/render_observability.py
deploy:
	uv run python scripts/cluster.py deploy
