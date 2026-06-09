# Contributing to WorkTicket

Thank you for considering contributing to WorkTicket. This document outlines the process and standards for contributions.

## Code of Conduct

This project and everyone participating in it is governed by the [Code of Conduct](./CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

1. Fork the repository.
2. Create a branch from `main` using a `feat/`, `fix/`, or `ops/` prefix.
3. Make your changes.
4. Run the project's checks (lint, typecheck, tests).
5. Submit a pull request.

## Development Workflow

### Prerequisites

- Docker and Docker Compose (for backend and infrastructure)
- Python 3.12+ (for backend development outside Docker)
- Node.js 20+ (for dashboard and mobile development)
- Expo CLI (for mobile development)

### Setting Up

```bash
# Clone your fork
git clone https://github.com/yourusername/WorkTicket.git
cd WorkTicket

# Install backend dependencies
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -e ".[test]"

# Install dashboard dependencies
cd ../web-dashboard
npm install

# Install mobile dependencies
cd ../mobile-app
npm install
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Static analysis chaos tests
cd chaos
python run_all.py
```

### Code Quality

- Run `ruff check` and `mypy` before opening a PR
- New billing logic and Celery tasks require tests
- Keep each PR to a single concern
- Never commit secrets — add new environment variables to `.env.example` with safe placeholder values

### Commit Messages

Use clear, descriptive commit messages. Reference issue numbers when applicable.

## Pull Request Process

1. Ensure all tests pass.
2. Update documentation (README, ops-guide, env examples) if your change affects them.
3. Update `ops-guide.md` if your change affects deploy order, environment variables, Redis key schema, or alert thresholds.
4. A maintainer will review your PR.

## Reporting Issues

Report bugs and suggest features via [GitHub Issues](https://github.com/WorkTicket/workticket/issues).

When reporting a bug, include:

- A clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, browser, versions)

## Security Issues

Do not report security vulnerabilities via public GitHub Issues. See [SECURITY.md](./SECURITY.md) for our disclosure policy.
