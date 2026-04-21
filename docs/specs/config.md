## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | >= 3.12 | Specified in `pyproject.toml` and `.python-version` |
| uv | latest | Package manager — [install guide](https://docs.astral.sh/uv/getting-started/installation/) |
| TeX Live | latest | Provides `pdflatex` and `bibtex` for compiling LaTeX reviews to PDF |

### Installing system dependencies

**Ubuntu / Debian:**

```bash
sudo apt-get update && sudo apt-get install -y texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-bibtex-extra biber
```

**macOS (Homebrew):**

```bash
brew install --cask mactex-no-gui
```

**Windows (WSL2):** Use the Ubuntu instructions inside your WSL distribution.

> **Note:** A minimal TeX Live installation (`texlive-latex-base`) is sufficient for most reviews, but `texlive-latex-extra` is recommended to avoid missing package errors. If `pdflatex` fails, the app falls back to `latexmk` automatically.

---

## Environment variables

Copy the example file and fill in your values:

```bash
cp .env_example .env
```

### LLM Configuration (required)

| Variable | Description | Example |
|---|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | `sk-or-v1-...` |
| `OPENROUTER_MODEL` | Model identifier for the pipeline | `deepseek/deepseek-v3.2` |
| `OPENROUTER_BASE_URL` | OpenRouter API endpoint | `https://openrouter.ai/api/v1` |

> Other models that work well: `google/gemini-3.1-flash-lite-preview`

### Observability (optional)

| Variable | Description | Default |
|---|---|---|
| `LANGFUSE_SECRET_KEY` | LangFuse secret key | (disabled if empty) |
| `LANGFUSE_PUBLIC_KEY` | LangFuse public key | (disabled if empty) |
| `LANGFUSE_HOST` | LangFuse server URL | (disabled if empty) |

When all three `LANGFUSE_*` variables are set, every LLM call and workflow step is traced. If any is missing, observability is silently disabled.

- **Cloud:** [cloud.lange.com](https://cloud.langfuse.com/) — sign up and create API keys in project settings
- **Self-hosted:** [langfuse.com/self-hosting](https://langfuse.com/self-hosting) — deploy via Docker

### Search behavior

| Variable | Default | Description |
|---|---|---|
| `OPENALEX_MAILTO` | `""` | Email for the OpenAlex polite pool (optional, raises rate limit) |
| `MAX_RESULTS_PER_SOURCE` | `3` | Papers fetched per source (arXiv / OpenAlex) per query |
| `MAX_REVIEW_ITERATIONS` | `3` | Max compose-evaluate retry loops for review quality |
| `MAX_AGENT_STEPS` | `10` | Max LLM tool-call steps for the Code-Act compose agent |

### Relevance filtering / quality control

| Variable | Default | Description |
|---|---|---|
| `MIN_REL_PAPERS` | `3` | Minimum REL/REL+ papers required to pass quality check |
| `MAX_SEARCH_ITERATIONS` | `3` | Max search retry iterations before accepting with a quality warning |
| `SKIP_REL_MINUS_DOWNLOAD` | `true` | Skip PDF download for REL- papers, use abstract instead |

### End-to-end evaluation (DeepEval)

| Variable | Default | Description |
|---|---|---|
| `DEEPEVAL_MODEL_NAME` | (uses `OPENROUTER_MODEL`) | Override model for evaluation LLM |

DeepEval reuses the `OPENROUTER_*` variables for its LLM calls. Only set `DEEPEVAL_MODEL_NAME` if you want a different model to judge the outputs.

---

## Installing and running

```bash
# Install Python dependencies
uv sync

# Launch the Streamlit web app
uv run streamlit run main.py
```

The app opens at [http://localhost:8501](http://localhost:8501). Enter a research topic in the sidebar and click **Run**.

A typical literature review takes 2–4 minutes to generate, depending on the model and number of search iterations.

---

## Running with Docker

Build and run in a single command (no local Python or TeX Live required):

```bash
docker build -t agentic-literature-review .
docker run --env-file .env -p 8501:8501 agentic-literature-review
```

Then open [http://localhost:8501](http://localhost:8501).

---

## Running tests

**Unit tests (no API calls):**

```bash
uv run pytest
```

**End-to-end evaluation (requires API access, costs tokens):**

```bash
uv run pytest evals/ -v
```

---

## How it works

The app runs a 9-node LangGraph state machine:

1. **expand_topic** — decomposes the topic into research directions
2. **form_search_queries** — generates arXiv search queries
3. **search** — queries arXiv + OpenAlex, deduplicates results
4. **filter_relevance** — scores each paper (NOT_REL / REL- / REL / REL+)
5. **evaluate_quality** — checks if enough relevant papers were found; retries if not
6. **form_additional_queries** — generates new queries for underrepresented directions
7. **download_and_summarize** — downloads PDFs, extracts text, summarizes each paper
8. **compose_review_latex** — Code-Act agent writes a LaTeX review
9. **evaluate_review** — LLM evaluates the review; if rejected, loops back to compose

Output is saved per-session under `sessions/` as JSON metadata, LaTeX source, and a compiled PDF.
