PYTHON ?= $(if $(shell test -x .venv/bin/python && printf yes),.venv/bin/python,python3.15)

.PHONY: help test lint format format-check check sync-main branch pr finish

help:
	@printf '%s\n' \
		'make test                 Run the test suite' \
		'make lint                 Run Ruff lint checks' \
		'make format               Format Python files with Ruff' \
		'make format-check         Check Python formatting' \
		'make check                Run lint, formatting checks, and tests' \
		'make sync-main            Switch to main and fast-forward from origin/main' \
		'make branch NAME=slug     Create and switch to codex/slug from main' \
		'make pr                   Check and push committed changes; create or reuse an open PR' \
		'make finish BRANCH=name   Update main and safely delete one fully merged local branch' \
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
	$(MAKE) check || exit $$?; \
	pr_url="$$(gh pr list --head "$$branch" --base main --state open \
		--json url,isCrossRepository --jq '.[] | select(.isCrossRepository == false) | .url')" || exit $$?; \
	git push -u origin "$$branch" || exit $$?; \
	if [ -n "$$pr_url" ]; then \
		printf 'Updated existing pull request: %s\n' "$$pr_url"; \
	else \
		gh pr create --base main --head "$$branch" --fill --draft \
			--body-file .github/pull_request_template.md; \
	fi

finish: export FINISH_BRANCH = $(BRANCH)
finish:
	@branch="$$FINISH_BRANCH"; \
	if [ -z "$$branch" ]; then \
		printf '%s\n' 'Usage: make finish BRANCH=codex/your-merged-branch'; \
		exit 1; \
	fi; \
	if [ "$$branch" = main ]; then \
		printf '%s\n' 'Cannot delete main.'; \
		exit 1; \
	fi; \
	if ! git check-ref-format "refs/heads/$$branch"; then \
		printf 'Invalid local branch name: %s\n' "$$branch"; \
		exit 1; \
	fi; \
	status="$$(git status --porcelain --untracked-files=all)" || exit $$?; \
	if [ -n "$$status" ]; then \
		printf '%s\n' 'Commit or stash all changes, including untracked files, before finishing a branch.'; \
		exit 1; \
	fi; \
	if ! git show-ref --verify --quiet "refs/heads/$$branch"; then \
		printf 'Cannot find local branch: %s\n' "$$branch"; \
		exit 1; \
	fi; \
	git fetch --prune origin || exit $$?; \
	if ! git merge-base --is-ancestor "refs/heads/$$branch" refs/remotes/origin/main; then \
		printf 'Cannot confirm that %s is fully merged into origin/main; no branch was deleted.\n' "$$branch"; \
		exit 1; \
	fi; \
	if ! git merge-base --is-ancestor refs/heads/main refs/remotes/origin/main; then \
		printf '%s\n' 'Local main is missing or has commits not in origin/main; update it manually first.'; \
		exit 1; \
	fi; \
	git switch main && \
	git merge --ff-only refs/remotes/origin/main && \
	git branch -d -- "$$branch"
