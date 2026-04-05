## How to run project?

### .env configuration

Copy .env_example and fill the environment variables

```
## LLM Configuration

OPENROUTER_API_KEY=""
OPENROUTER_MODEL=""
OPENROUTER_BASE_URL""

## Observability

LANGFUSE_SECRET_KEY=""
LANGFUSE_PUBLIC_KEY=""
LANGFUSE_HOST=""

## Search

# Email for OpenAlex polite pool (optional but recommended, raises rate limit)
OPENALEX_MAILTO=""
# Results fetched per source per query (default: 3);
MAX_RESULTS_PER_SOURCE=""
```

### LangFuse

It is needed to fill `LANGFUSE_*` env variables. 

Use self-hosted or cloud LangFuse for observability platform.

Self-hosting information: https://langfuse.com/self-hosting

Cloud LangFuse: https://cloud.langfuse.com/

### Running the project

After configuring .env file it is as simple as:

```bash
uv sync
```

```bash
uv run streamlit run main.py
```