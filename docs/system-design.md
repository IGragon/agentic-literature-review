## Key architecture decisions



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
Less than 5 minutes per literature review

**Cost**
Less than 1$ per literature review

**Reliability**

Over 90% success rate for arbitrary inputs not ouside the scope of literature review queries.
