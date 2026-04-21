## Observability

LangFuse is used as an observability platform to track workflow flow:
- Session: starts at user query and ends with recieved output
- Trace: starts at LLM/Agent recieving control
- Span: step inside a trace
- Event: tool-call or api usage

## Evals

### Static benchmark

From known articles we take introduction and prior work sections.

Construct a dataset with the samples containing the following components:
- Article name: that would be used as an input for the pipeline
- Mentioned articles: a collection of research papers cited by corresponding article

There we measure Recall and Precision of articles retrieved by workflow (before and after relevance filtering).

### End-to-End assessment

For end-to-end assessment DeepEval is used to evaluate the resulting literature review.

**Inputs:** a list of topics for literature review (stored in `evals/dataset.json`).

**Metrics (3):**

1. **Faithfulness** (`FaithfulnessMetric`, threshold=0.7) — Checks whether the review is grounded in the paper summaries (retrieval context). Measures internal consistency: claims in the review should be supported by the source paper summaries, not hallucinated.

2. **Coherence** (`GEval`, threshold=0.7) — Custom LLM-as-a-Judge metric evaluating logical flow and academic writing quality. Criteria: structure (proper sections), flow (smooth transitions), synthesis (comparing papers vs. listing them), clarity (academic language), completeness relative to topic and research directions.

3. **Citation Correctness** (`GEval`, threshold=0.7) — Custom LLM-as-a-Judge metric evaluating citation usage. Criteria: proper `\cite{key}` format, all papers cited at least once, no fabricated citation keys, accurate attribution of claims to cited papers, bibliography completeness.

**Evaluation flow:**
- Each topic runs through the full pipeline (`AgenticLiteratureReview`)
- Pipeline outputs (review text, paper summaries, directions) are mapped to `LLMTestCase` fields
- `assert_test` evaluates with all three metrics; score >= 0.7 per metric = PASS

**Results:** average grade across topics per metric.

**Implementation:** `evals/` directory — see `evals/test_e2e_review.py` for the pytest integration. Run with `pytest evals/ -v`.

**LLM for evaluation:** Uses the same OpenRouter model as the pipeline (configured via `OPENROUTER_*` env vars, mapped to `OPENAI_*` in `evals/conftest.py`).
