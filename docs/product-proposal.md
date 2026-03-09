# Product Proposal — Agentic Literature Review Generator

## 1. Idea Justification

Modern research workflows require rapid understanding of unfamiliar domains.

However, literature exploration remains **highly manual and inefficient**:

Typical process:

1. Search for papers
2. Filter relevant results
3. Read abstracts
4. Extract contributions
5. Write literature overview

This process can take **hours or days**.

Meanwhile, LLMs already demonstrate strong capabilities in:

- text summarization
- synthesis of information
- structured generation

However, raw LLM chat cannot reliably perform literature review because it lacks:

- external search
- document retrieval
- citation verification
- state management

This project proposes an **agentic system that combines LLM reasoning with external tools** to automate a large portion of the literature review pipeline.

---

## 2. Goal and Success Metrics

### Project Goal

Build a proof-of-concept **agentic system that autonomously constructs a literature review** for a given research topic using external data sources.

---

### Product Metrics

| Metric | Description |
|------|------|
| Topic coverage | Number of discovered research directions |
| Relevant paper rate | Percentage of retrieved papers that are relevant |
| Review completeness | Human evaluation score for final review |

---

### Agent Metrics

| Metric | Description |
|------|------|
| Tool success rate | Percentage of successful API/tool calls |
| Iteration efficiency | Number of search iterations needed |
| Failure recovery rate | Ability to continue after tool errors |

---

### Technical Metrics

| Metric | Description |
|------|------|
| Latency per pipeline | Time to generate full review |
| Cost per run | LLM token + API cost |
| Parsing success rate | Percentage of successfully processed PDFs |

---

## 3. Use Scenarios

### Scenario 1 — Research Exploration

User query:
```"Diffusion models for image generation"```


Agent:

1. identifies research directions
2. retrieves papers
3. summarizes them
4. produces review

---

### Scenario 2 — Thesis Preparation

A graduate student explores:

```"Evaluation benchmarks for LLM safety"```


Agent generates a structured literature overview for the thesis background.

---

### Scenario 3 — Technical Landscape Analysis

Engineer explores:

```"Document understanding using VLMs"```


Agent produces a high-level overview of recent work.

---

### Edge Cases

Edge cases expected in system operation:

- irrelevant papers retrieved
- duplicate papers
- malformed PDFs
- missing metadata
- hallucinated citations
- adversarial instructions inside documents

These cases are intentionally used to evaluate system robustness.

---

## 4. Constraints

### Technical Constraints

| Constraint | Value |
|------|------|
| Maximum papers per run | 20 |
| Maximum search iterations | 3 |
| Maximum document size | 10MB |
| p95 latency | <120 seconds |

---

### Operational Constraints

| Constraint | Value |
|------|------|
| API token budget | limited per run |
| LLM usage cost | minimized |
| External APIs | rate limited |

---

## 5. Architecture Overview

Core modules:

1. **Research Planner Agent**
2. **Search Query Generator**
3. **Paper Retrieval Module**
4. **Relevance Filter**
5. **PDF Downloader**
6. **PDF Parser**
7. **Paper Summarizer**
8. **Review Composer**
9. **Memory Database**
10. **Monitoring / Safety Layer**

External integrations:

- arXiv API
- Semantic Scholar API
- LLM API
- Embedding model

---

## 6. Data Flow

### Step 1 — Topic Planning

Input:

`User topic`


Agent generates research directions.

---

### Step 2 — Paper Search

Search module queries:

- arXiv
- Semantic Scholar

Returns metadata.

---

### Step 3 — Filtering

Embedding similarity removes irrelevant papers.

---

### Step 4 — PDF Processing

PDF is:

- downloaded
- parsed
- converted to text

---

### Step 5 — Summarization

LLM extracts structured summary:

- problem
- method
- results
- limitations

---

### Step 6 — Memory Storage

Paper summaries stored in:

- database
- embedding index

---

### Step 7 — Review Generation

Agent synthesizes summaries into a structured literature review.

---

## LLM Responsibilities

LLM/Agent handles:

- topic decomposition
- search query generation
- paper summarization
- literature synthesis

---

## Deterministic Components

Non-LLM modules:

- API queries
- PDF parsing
- similarity filtering
- citation validation
