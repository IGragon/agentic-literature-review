## Key architecture decisions

**1. OpenRouter as the LLM interface**
Rather than committing to a single LLM provider, all LLM calls go through OpenRouter. This allows model swapping via config and enables a priority-ordered fallback list if a model is unavailable.

**2. Search is a workflow stage, not an agentic tool**
Article retrieval is a fixed pipeline stage (generate queries -> fetch -> deduplicate -> filter), not a tool the agent calls freely. This trades flexibility for predictability and cost control.

**3. Dual-source retrieval with deduplication**
Both arXiv and OpenAlex are queried for every search request. Results are deduplicated and merged to maximize recall while tolerating the failure of either source.

**4. Tiered LLM-based relevance scoring**
Relevance filtering uses four grades (NOT_REL, REL-, REL, REL+) rather than a binary pass/fail. This preserves borderline articles that might otherwise be discarded, and lets the system degrade gracefully when recall is low.

**5. Iterative retrieval with LLM-eval recall check**
The system reruns search up to N times if a self-evaluation step deems retrieved articles insufficient. Same retry loop applies to review composition. Hard iteration caps enforce the latency and cost constraints.

**6. LaTeX as output format with compile-time validation**
The review is composed and validated as LaTeX (with BibTeX), not plain text. A `compile_latex` tool provides a deterministic correctness signal (OK vs. ERROR + trace) that the agent can act on without hallucinating whether citations are valid.

**7. Jinja2 prompt templates**
All LLM prompts are Jinja2 templates, not hardcoded strings. This separates prompt logic from application code and makes iteration on prompts cheaper.

**8. LangFuse for observability**
Every session, LLM trace, step span, and tool call is tracked in LangFuse. This is essential for debugging iterative agentic workflows where failures may occur deep in a multi-step run.

**9. Streamlit for the PoC UI**
Streamlit is chosen for simplicity at PoC scale. It supports live workflow progress display and session history access without requiring a dedicated backend or frontend build step.

**10. LLM Guard at the input boundary**
User input is validated with LLM Guard before any workflow execution begins. This prevents adversarial or off-scope queries from consuming pipeline resources.

## Module list

- **Streamlit webapp**: simple user interface for PoC.
- **Literature review agent**: end-to-end agentic literature review.
- **Article retrieval module** (Search module): getting articles that might be helpful for conducting literature review on specified topic.
- **Relevance assessment module** (a part or separate from Search module): to leave out only relevant, useful, and high-quality (complete) articles.
- **Session storage**: to keep the history of queries for revisiting in future.
- **Observability**: LangFuse to track workflow traces.
- **Testing module**: for static and llm-as-a-judge benchmarking.

## Main workflow

High-level workflow

**Input:** User Query with the description of a scientific field or paper direction.

↓

Validate that the query seems relevant for our system.

↓

User Query decomposition into relevant research directions and construction of search queries.

↓

Retrieval of articles, relevance filtering, summarization of selected articles.

↓

Literature review composition in Latex based on selected research directions and found articles.

↓

**Output:** .pdf with literature review and correct citations and dynamically updated UI with progress.

## State, Memory, Context

Session state (per User Query):
- User Query.
- Literature review research directions.
- Articles: main information, citation format, summary.
- Generated literature review.

State passed between nodes in workflow:
- User Query
- Research directions
- Articles
- Articles retrieval attempt (equivalently number of iterations left)
- Literature review generation iteration (equivalently number of iterations left)

Context for each LLM call is derived dynamically, depending on the workflow stage and prompt structure. Prompts are Ninja2 templates.

## Retrieval contour

Search tools (workflow stage) 

High-level flow for each query:
- Fetch results from arxiv and openalex
- Deduplicate results
- Return articles in defined structure

Next, after all queries have been processed:
- Deduplicate results once again
- Perform relevance assessment and filtration (NOT_REL, REL-, REL, REL+)

Perform additional requests (up to N times) if recall is not satisfactory (LLM-eval).

## Tools and API-integrations

LLM interface is OpenRouter API for flexibility of model selection.

### Search Tools

Search is not quite a "tool" in agentic sense. It is more of a "stage" in a workflow.

Used APIs:
- arXiv API (article retrieval)
- OpenAlex API (article retrieval)
- doi org citation API (bibtex citation from DOI)


### Writing Tools

- write_latex
- read_latex
- write_bibliography
- read_bibliography
- compile_latex (returns OK if successful or ERROR w/ trace otherwise)


## Guardrails, Fallbacks, and Failure modes 

Guardrails: LLM Guard for user input validation.

Fallbacks: Priority list of LLMs with OpenRouter

Failure modes:
- if either paper search api is unavailable -- the second one could partially compensate.
- if relevant articles are not found (i.e empty list after relevance filtering after several search iterations), then the workflow should fail with "Failed to fetch relevant articles to the provided topic". In order not to feed user gibberish.
- if quality of retrieved papers is not enough after several search attempts, then we the review will be marked as of "low quality" or we could ask the user if they want to continue.
- if OpenRouter API is not available then this error should be displayed.

## Technical and operational constraints

**Latency:**
Less than 15 minutes per literature review

**Cost**
Less than 1$ per literature review

**Reliability**

Over 90% success rate for arbitrary inputs not ouside the scope of literature review queries.
