# Contributing to hiil

Thanks for taking the time to contribute! This guide explains how to set up the
project, run checks, and submit changes.

## Code of Conduct

This project and everyone participating in it is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to
uphold this code.

## Getting Started

### Prerequisites

- Python 3.13+ (3.14 supported)
- Node.js 20+ and npm (frontend only)
- [uv](https://docs.astral.sh/uv/) or pip

### Setup

```bash
# Backend (install editable package + dev deps)
uv pip install -e ".[dev]"

# Frontend
cd canvas_app/frontend
npm install
```

## Running Checks

```bash
# Backend
make lint          # ruff check
make format-fix    # ruff format
make typecheck     # mypy static analysis
make test          # pytest -x -q
make check         # lint + typecheck + test (CI pipeline)

# Frontend
cd canvas_app/frontend
npx eslint src/    # lint
npx vitest run     # unit tests (21 tests)
npx vite build     # production build
```

CI (`.github/workflows/ci.yml`) runs ruff, mypy, and pytest on Python 3.13 and
3.14 for every push and PR to `main`. Your PR must pass all of them.

## Branching Strategy

- `main` is the stable branch. All commits to `main` must come through a pull
  request (or be direct, small, verified fixes by maintainers).
- Use descriptive feature branches, e.g. `fix/status-endpoint`,
  `feat/voice-input`, `docs/api-reference`.

## Commit Message Style

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

examples:
feat(voice): add WebSocket streaming for STT
fix(chat): auto-create conversation on first message
chore(deps): pin eslint to v8
docs: add security policy
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`,
`ci`, `chore`, `revert`.

## Submitting a Pull Request

1. Fork the repository and create a branch from `main`.
2. Make your changes. Keep them focused and small.
3. Add or update tests for your changes (backend: `tests/`, frontend:
   `src/**/*.test.{js,jsx}`).
4. Run all checks above and make sure they pass.
5. Commit with a Conventional Commits message.
6. Open a pull request against `main` using the PR template.
7. In the PR description, summarize the change, how it was tested, and any
   screenshots if the change is visual.

## Issue Reporting

- Use the [bug report](.github/ISSUE_TEMPLATE/bug_report.yml) template for
  bugs — include steps to reproduce and expected/actual behavior.
- Use the [feature request](.github/ISSUE_TEMPLATE/feature_request.yml)
  template for new ideas.
- For security vulnerabilities, see [SECURITY.md](SECURITY.md) — do **not**
  open a public issue.
