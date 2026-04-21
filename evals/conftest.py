"""Conftest for DeepEval end-to-end evaluations.

Validates that required environment variables are set before running
evaluation tests. The actual OpenRouter client is configured in
metrics.py via the OpenRouterModel class.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()


def pytest_collection_modifyitems(config, items):
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.exit(
            "OPENROUTER_API_KEY not set. Set it in .env or as an environment variable.",
            returncode=2,
        )
    for item in items:
        item.add_marker(pytest.mark.e2e)
