"""DeepEval metric definitions for literature review evaluation.

Metrics are created lazily via get_metrics() to defer model client
initialization until after conftest.py has set the environment variables.

A custom OpenRouterModel is used instead of DeepEval's default GPTModel
because DeepEval's built-in model calls beta.chat.completions.parse()
(structured outputs), which OpenRouter does not support.
"""

from __future__ import annotations

import os

from deepeval.metrics import FaithfulnessMetric, GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCaseParams
from openai import AsyncOpenAI, OpenAI


class OpenRouterModel(DeepEvalBaseLLM):
    """DeepEval-compatible model that uses OpenRouter via the OpenAI SDK.

    Uses standard chat.completions.create() instead of the beta structured
    output endpoint, which OpenRouter does not support.
    """

    def __init__(self, model: str, api_key: str, base_url: str):
        self._model_name = model
        self._api_key = api_key
        self._base_url = base_url
        self._sync_client: OpenAI | None = None
        self._async_client: AsyncOpenAI | None = None
        super().__init__(model=model)

    def load_model(self):
        self._sync_client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        self._async_client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._sync_client

    def _extra_kwargs(self, schema) -> dict:
        if schema is not None:
            return {"response_format": {"type": "json_object"}}
        return {}

    def generate(self, prompt: str, **kwargs) -> str:
        response = self._sync_client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
            **self._extra_kwargs(kwargs.get("schema")),
        )
        return response.choices[0].message.content

    async def a_generate(self, prompt: str, **kwargs) -> str:
        response = await self._async_client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
            **self._extra_kwargs(kwargs.get("schema")),
        )
        return response.choices[0].message.content

    def get_model_name(self) -> str:
        return f"openrouter/{self._model_name}"


def _get_model() -> OpenRouterModel:
    return OpenRouterModel(
        model=os.environ.get("DEEPEVAL_MODEL_NAME", os.environ.get("OPENROUTER_MODEL", "")),
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        base_url=os.environ.get("OPENROUTER_BASE_URL", ""),
    )


_COHERENCE_CRITERIA = """\
Evaluate whether the literature review demonstrates coherent logical flow \
and academic writing quality. Consider:

1. STRUCTURE: Does the review follow a logical organization with clear \
sections (Introduction, topic-specific sections, Synthesis/Discussion, \
Open Problems, Conclusion)?

2. FLOW: Do paragraphs transition smoothly from one idea to the next? \
Are connections between papers and concepts explicitly stated?

3. SYNTHESIS: Does the review synthesize findings across papers rather \
than merely listing them sequentially? Are comparisons and contrasts drawn?

4. CLARITY: Is the writing clear and precise? Does it use appropriate \
academic language? Are technical terms used correctly?

5. COMPLETENESS relative to context: Does the review address the stated \
topic and research directions provided in the context?"""

_CITATION_CRITERIA = """\
Evaluate whether the literature review uses citations correctly and does \
not fabricate references. Consider:

1. CITATION FORMAT: Are citations in the text using proper \\cite{key} \
format? Are they integrated into sentences naturally?

2. COVERAGE: Does the review cite papers that are listed in the \
retrieval context? Every paper from the retrieval context should be \
referenced at least once in the body of the review.

3. NO FABRICATION: Does the review avoid citing papers or using citation \
keys that do not appear in the retrieval context? Fabricated citations \
are a serious academic integrity violation.

4. ACCURACY: When the review attributes a claim to a cited paper, is \
that attribution consistent with what the paper's summary describes? \
Claims should not misrepresent the cited work.

5. BIBLIOGRAPHY: Are all cited papers reflected in the bibliography?"""


def get_metrics() -> list:
    """Create and return the three evaluation metrics.

    Must be called after conftest.py has configured the environment variables.
    """
    model = _get_model()
    return [
        FaithfulnessMetric(threshold=0.7, include_reason=True, model=model),
        GEval(
            name="Coherence",
            criteria=_COHERENCE_CRITERIA,
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
            threshold=0.7,
            model=model,
        ),
        GEval(
            name="Citation Correctness",
            criteria=_CITATION_CRITERIA,
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.RETRIEVAL_CONTEXT],
            threshold=0.7,
            model=model,
        ),
    ]
