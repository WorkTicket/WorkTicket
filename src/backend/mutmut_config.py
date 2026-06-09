"""Mutation testing configuration for mutmut.

Targets the AI validator, billing state machine, and quota engine
as the highest-risk code paths.

Usage:
    mutmut run --paths-to-mutate app/ai/validator.py app/billing/state_machine.py app/billing/quota_engine.py
"""

# Paths to mutate (highest impact / most critical logic)
PATHS_TO_MUTATE = [
    "app/ai/validator.py",
    "app/billing/state_machine.py",
    "app/billing/quota_engine.py",
    "app/billing/cost_estimator.py",
    "app/pricing/engine.py",
]

# Test runner command
TEST_RUNNER = "cd src/backend && python -m pytest tests/ -x --tb=short -q"

# Minimum mutation score threshold (percentage)
MIN_MUTATION_SCORE = 70

# Number of mutations to run in parallel
PARALLEL = 4

# Timeout per test run (seconds)
TEST_TIMEOUT = 120
