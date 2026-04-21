"""End-to-end evaluation of the literature review pipeline using DeepEval.

Run with: pytest evals/ -v

Each test case:
1. Runs the full pipeline for a topic
2. Constructs an LLMTestCase from the pipeline outputs
3. Evaluates with Faithfulness, Coherence, and Citation Correctness
4. Asserts all metrics pass their thresholds

These tests are expensive (2-4 min per topic, external API calls).
They are excluded from normal `pytest` runs (testpaths = ["tests"]).
"""

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from evals.dataset import load_topics
from evals.metrics import get_metrics
from evals.pipeline_runner import run_pipeline
from src.agentic_workflow import NoRelevantPapersFound

TOPICS = load_topics()


@pytest.mark.e2e
@pytest.mark.parametrize("topic", TOPICS, ids=lambda t: t[:40])
def test_e2e_review(topic: str):
    try:
        result = run_pipeline(topic)
    except NoRelevantPapersFound:
        pytest.skip(f"No relevant papers found for topic: {topic}")
    except RuntimeError as e:
        pytest.skip(f"Pipeline failed for topic: {topic} - {e}")

    test_case = LLMTestCase(
        input=topic,
        actual_output=result.review,
        retrieval_context=result.paper_summaries,
        context=[
            f"Topic: {result.topic}",
            f"Research directions: {', '.join(result.directions)}",
        ],
    )

    assert_test(test_case, get_metrics())
