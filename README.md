# Agentic Literature Review Generator

## What is this project?

**Agentic Literature Review Generator** is a proof-of-concept agentic system that automatically searches, analyzes, and synthesizes academic papers into a structured literature review.

The system takes a **research topic** as input and autonomously:

1. Decomposes the topic into research directions.
2. Generates search queries and retrieves papers from arXiv and OpenAlex.
3. Scores relevance using an LLM (tiered: NOT_REL / REL- / REL / REL+).
4. Downloads and summarizes relevant papers.
5. Produces a compiled LaTeX literature review (PDF).

The PoC demonstrates how **LLM-driven agents can orchestrate external tools and data sources** to perform a research workflow that typically requires hours of manual work. A **Streamlit webapp** provides the UI with live progress tracking and session history.

---

## Problem

Researchers, graduate students, and engineers often spend **many hours collecting and reading papers** when starting a new research topic.

Typical workflow today:

1. Search papers on arXiv / Google Scholar
2. Read abstracts
3. Filter relevant work
4. Extract methods and results
5. Write literature review manually

Pain points:

- Searching is iterative and noisy
- Many irrelevant papers appear
- Important papers are missed
- Summaries are time-consuming
- Literature reviews quickly become outdated

---

## Target Users

Primary users:

- Graduate students starting a new research topic
- Researchers exploring unfamiliar subfields
- Engineers doing technical landscape analysis
- Hackathon / competition participants

---

## Architecture & Workflow

The system is built as a **9-node LangGraph state machine** with two iterative quality loops:

```
User Topic
    │
    ▼
1. expand_topic         — decompose topic into research directions
    │
    ▼
2. form_search_queries  — generate arXiv/OpenAlex search queries
    │
    ▼
3. search               — query arXiv + OpenAlex, deduplicate results
    │
    ▼
4. filter_relevance     — LLM scores each paper (NOT_REL/REL-/REL/REL+)
    │
    ▼
5. evaluate_quality     — enough REL/REL+ papers?
    │                        │
    ├── no ──► 6. form_additional_queries ──► (back to step 3, max N times)
    │
    ▼ yes
7. download_and_summarize — download PDFs, extract text, summarize each paper
    │
    ▼
8. compose_review_latex   — Code-Act agent writes LaTeX review via tool calls
    │
    ▼
9. evaluate_review        — LLM judges review quality
    │                        │
    ├── rejected ──► (back to step 8, max N times with feedback)
    │
    ▼ accepted
Output: compiled PDF + LaTeX source
```

**Key design decisions** (detailed in `docs/system-design.md`):

- **OpenRouter** as the LLM interface with model-agnostic fallback
- **arXiv + OpenAlex** dual-source retrieval with deduplication
- **Tiered relevance scoring** (4 grades) instead of binary pass/fail
- **LaTeX compilation** provides deterministic citation validation
- **Jinja2** prompt templates separated from application code
- **LangFuse** observability on every LLM call and workflow step
- **Streamlit** for the PoC UI with live progress and session history

---

## What the PoC Demonstrates

The proof-of-concept system demonstrates an **autonomous research pipeline**:

1. **Topic decomposition**
   - LLM expands the user topic into 1–5 specific research directions

2. **Dual-source paper retrieval**
   - Queries arXiv and OpenAlex APIs in parallel
   - Deduplicates results by DOI and arXiv ID

3. **Tiered relevance filtering**
   - LLM scores each paper with 4-grade relevance (NOT_REL / REL- / REL / REL+)
   - Removes irrelevant and low-completeness borderline papers

4. **Iterative search with quality check**
   - Retries search with new queries if not enough relevant papers found
   - Falls back with a quality warning after exhausting retries

5. **PDF download and summarization**
   - Downloads arXiv PDFs (skips REL- if configured)
   - Extracts text via pypdf, falls back to abstract if full text unavailable
   - LLM extracts structured summaries (Problem / Method / Results / Limitations)

6. **Code-Act LaTeX composition**
   - Agent iteratively writes BibTeX + LaTeX, compiles, and fixes errors
   - Uses 5 scoped tools: write_bib, read_bib, write_tex, read_tex, compile
   - Compile tool returns OK or ERROR+trace for deterministic feedback

7. **LLM-as-a-judge review evaluation**
   - Evaluates coverage, synthesis, citations, structure, and research gaps
   - Rejects and feeds back to the compose agent until accepted (up to N times)

8. **Observability and monitoring**
   - LangFuse traces every session, LLM call, tool call, and workflow step
   - Logs search queries, paper metadata, errors, and pipeline events

The result is a **compiled PDF literature review with validated citations**, generated automatically.

---

## What the PoC Does NOT Do (Out of Scope)

The PoC intentionally avoids large-scale production features.

Out of scope:

- Full academic-grade literature reviews
- Perfect citation coverage
- Multi-language research analysis
- Citation network exploration at scale
- Fine-grained methodological comparison between papers
- Automated experiments reproduction
- Real-time updates of literature databases
- Large-scale crawling of publisher platforms
- Paywalled paper retrieval (arXiv open-access PDFs only)
- Multi-paper authoring workflows

The PoC focuses on **demonstrating an agentic research workflow**, not replacing human literature review.

---

## Key Demonstrated Concepts

This project demonstrates several core **Agentic AI system design patterns**:

- **Tool-using agents** — LLM calls scoped LaTeX tools in a Code-Act loop
- **Multi-step planning** — 9-node LangGraph state machine with conditional routing
- **External knowledge retrieval** — dual-source search with deduplication
- **LLM-as-a-judge** — quality evaluation drives iterative self-improvement
- **Deterministic validation** — LaTeX compilation as ground truth for citation correctness
- **Tiered decision boundaries** — 4-grade relevance scoring instead of binary classification
- **State management** — LangGraph state flows between nodes with iteration tracking
- **Failure detection and recovery** — transient LLM errors retried; compilation errors fed back to agent
- **Observability** — LangFuse traces every session, span, generation, and tool event

---

## Example Input

```
Topic: "Prompt injection attacks in LLM agents"
```

## Example Output

A compiled PDF literature review displayed inline in the Streamlit UI, including:

- Research directions
- Key papers with relevance badges and BibTeX citations
- Structured summary per paper (Problem / Method / Results / Limitations)
- Synthesized review sections per research direction
- Open research problems
- Downloadable PDF and LaTeX source (.tex)

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python >= 3.12 |
| Workflow engine | LangGraph |
| LLM interface | OpenRouter (model-agnostic, provider fallback) |
| LLM framework | LangChain (ChatOpenRouter, tools, structured output) |
| Search APIs | arXiv API + OpenAlex API |
| PDF parsing | pypdf |
| Prompt templating | Jinja2 |
| UI | Streamlit (live progress, session history, PDF viewer) |
| Observability | LangFuse (traces, spans, generations, events) |
| Output format | LaTeX (compiled to PDF via pdflatex + bibtex, latexmk fallback) |
| Session storage | JSON files under `sessions/` |
| Testing | pytest (unit) + DeepEval (end-to-end LLM-as-a-judge) |
| Containerization | Docker |

---

## Setup & Running

### Prerequisites

- **Python >= 3.12** and **uv** (package manager)
- **TeX Live** (`pdflatex` + `bibtex`) — see `docs/specs/config.md` for platform-specific install instructions
- **OpenRouter API key** — sign up at [openrouter.ai](https://openrouter.ai)

### Quick start

```bash
cp .env_example .env          # edit .env with your OpenRouter key + model
uv sync                        # install dependencies
uv run streamlit run main.py   # opens at http://localhost:8501
```

### Docker

```bash
docker build -t agentic-literature-review .
docker run --env-file .env -p 8501:8501 agentic-literature-review
```

### Running tests

```bash
uv run pytest           # unit tests (no API calls)
uv run pytest evals/ -v # end-to-end evaluation (requires API access)
```

Typical runtime: **2–4 minutes** per literature review.

---

## Configuration

All behavior is configured via environment variables (see `.env_example`):

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | *(required)* | OpenRouter API key |
| `OPENROUTER_MODEL` | *(required)* | Model identifier (e.g. `deepseek/deepseek-v3.2`) |
| `MAX_RESULTS_PER_SOURCE` | `3` | Papers per source per query |
| `MAX_SEARCH_ITERATIONS` | `3` | Max search retries before quality warning |
| `MIN_REL_PAPERS` | `3` | Min REL/REL+ papers required |
| `SKIP_REL_MINUS_DOWNLOAD` | `true` | Skip PDF download for REL- papers |
| `MAX_REVIEW_ITERATIONS` | `3` | Max compose-evaluate iterations |
| `MAX_AGENT_STEPS` | `10` | Max Code-Act tool-call steps |
| `LANGFUSE_*` | *(optional)* | Observability (disabled if unset) |
| `OPENALEX_MAILTO` | `""` | Email for OpenAlex polite pool |

Full details: `docs/specs/config.md`

---

## Project Goal

Demonstrate a **robust agentic system capable of orchestrating multiple tools and reasoning steps to produce a coherent literature review** under operational constraints and failure scenarios.
