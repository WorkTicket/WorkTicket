# Item 13 — Dependency Audit CI Configuration

## Dependabot Configuration
Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/src/backend"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "security"
    assignees:
      - "team-lead"

  - package-ecosystem: "npm"
    directory: "/src/web-dashboard"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "security"

  - package-ecosystem: "npm"
    directory: "/src/mobile-app"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "security"
    ignore:
      - dependency-name: "expo*"
        update-types: ["version-update:semver-patch"]
```

## CI Pipeline (extend existing `.github/workflows/ci.yml`)

```yaml
# Add to ci.yml jobs
security-audit:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    
    - name: Python dependency audit
      working-directory: ./src/backend
      run: |
        pip install pip-audit
        pip-audit --requirement requirements.txt --desc on

    - name: npm audit (web-dashboard)
      working-directory: ./src/web-dashboard
      run: npm audit --audit-level=high

    - name: npm audit (mobile-app)
      working-directory: ./src/mobile-app
      run: npm audit --audit-level=high
```

## Pre-commit Hook for Local Audits
Create `.pre-commit-config.yaml` section:

```yaml
repos:
  - repo: https://github.com/pypa/pip-audit
    rev: v2.7.0
    hooks:
      - id: pip-audit
        args: [--requirement, src/backend/requirements.txt]
```

## Scheduled Audit Job
Create `.github/workflows/dependency-audit.yml`:

```yaml
name: Weekly Dependency Audit
on:
  schedule:
    - cron: "0 6 * * 1"  # Every Monday 6AM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: pip-audit
        run: |
          pip install pip-audit
          pip-audit --requirement src/backend/requirements.txt --desc on --format markdown --output audit-report.md

      - name: npm audit web-dashboard
        working-directory: ./src/web-dashboard
        run: npm audit --audit-level=high --json > npm-audit-web.json || true

      - name: npm audit mobile-app
        working-directory: ./src/mobile-app
        run: npm audit --audit-level=high --json > npm-audit-mobile.json || true

      - name: Upload audit reports
        uses: actions/upload-artifact@v4
        with:
          name: dependency-audit-reports
          path: |
            audit-report.md
            npm-audit-*.json
```

## Alerting Thresholds
| Severity | Action | SLA |
|---|---|---|
| Critical | Blocking CI, auto-create P0 ticket | <24h |
| High | Non-blocking CI, auto-create P1 ticket | <72h |
| Moderate | PR comment, manual review | Next sprint |
| Low | Logged in audit report | Triage as needed |
