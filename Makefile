PYTHON ?= $(if $(shell test -x .venv/bin/python && printf yes),.venv/bin/python,python3.15)

.PHONY: help test lint format format-check check sync-main branch pr

help:
	@printf '%s\n' \
		'make test                 Run the test suite' \
		'make lint                 Run Ruff lint checks' \
		'make format               Format Python files with Ruff' \
		'make format-check         Check Python formatting' \
		'make check                Run lint, formatting checks, and tests' \
		'make sync-main            Switch to main and fast-forward from origin/main' \
		'make branch NAME=slug     Create and switch to codex/slug from main' \
		'make pr                   Require committed changes, check, push, and open a draft PR with checklist' \
		'Python: executable .venv/bin/python, otherwise python3.15; override with PYTHON=...'

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

format-check:
	$(PYTHON) -m ruff format --check .

check: lint format-check test

sync-main:
	git switch main
	git pull --ff-only origin main

branch:
	@if [ -z "$(NAME)" ]; then \
		printf '%s\n' 'Usage: make branch NAME=short-description'; \
		exit 1; \
	fi
	@branch="$$(git branch --show-current)" || exit $$?; \
	if [ "$$branch" != "main" ]; then \
		printf '%s\n' 'Create feature branches from main. Run make sync-main first.'; \
		exit 1; \
	fi; \
	git switch -c "codex/$(NAME)"

pr:
	@if ! command -v gh >/dev/null 2>&1; then \
		printf '%s\n' 'GitHub CLI (gh) is required for make pr.'; \
		exit 1; \
	fi
	@branch="$$(git branch --show-current)" || exit $$?; \
	if [ -z "$$branch" ]; then \
		printf '%s\n' 'Could not determine the current branch.'; \
		exit 1; \
	fi; \
	if [ "$$branch" = "main" ]; then \
		printf '%s\n' 'Switch to a feature branch before opening a PR.'; \
		exit 1; \
	fi; \
	status="$$(git status --porcelain --untracked-files=all)" || exit $$?; \
	if [ -n "$$status" ]; then \
		printf '%s\n' 'Commit or stash all changes, including untracked files, before opening a PR.'; \
		exit 1; \
	fi; \
	if [ ! -f .github/pull_request_template.md ] || [ ! -r .github/pull_request_template.md ]; then \
		printf '%s\n' 'PR checklist template is missing or unreadable: .github/pull_request_template.md'; \
		exit 1; \
	fi; \
	$(MAKE) check && \
	git push -u origin "$$branch" && \
	gh pr create --fill --draft --body-file .github/pull_request_template.md
