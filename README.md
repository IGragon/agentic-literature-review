# Agentic Literature Review Generator

## What is this project?

**Agentic Literature Review Generator** is a proof-of-concept agentic system that automatically searches, analyzes, and synthesizes academic papers into a structured literature review.

The system takes a **research topic** as input and autonomously:

1. Identifies relevant research directions.
2. Searches for scientific papers.
3. Downloads and analyzes the papers.
4. Produces a structured literature review.

The PoC demonstrates how **LLM-driven agents can orchestrate external tools and data sources** to perform a research workflow that typically requires hours of manual work.

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

## What the PoC Demonstrates

The proof-of-concept system demonstrates an **autonomous research pipeline**:

1. **Topic planning agent**
   - Expands the user topic into multiple research directions

2. **Paper retrieval**
   - Queries external APIs (e.g. arXiv / Semantic Scholar)

3. **Relevance filtering**
   - Filters retrieved papers using embeddings

4. **PDF parsing and summarization**
   - Extracts text from papers and produces structured summaries

5. **Literature review synthesis**
   - Generates a structured review document (Markdown or LaTeX)

6. **Monitoring and safety checks**
   - Detects hallucinated citations
   - Handles parsing failures
   - Logs system behavior

The result is a **draft literature review with citations** generated automatically.

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
- Paywalled paper retrieval

The PoC focuses on **demonstrating an agentic research workflow**, not replacing human literature review.

---

## Key Demonstrated Concepts

This project demonstrates several core **Agentic AI system design patterns**:

- Tool-using agents
- Multi-step planning
- External knowledge retrieval
- Memory and state management
- Failure detection and monitoring
- Security considerations (prompt injection from documents)

---

## Example Input

```Topic: "Prompt injection attacks in LLM agents"```
 

## Example Output

A generated literature review including:

- Research directions
- Key papers
- Summary of approaches
- Open research problems
- Structured citations

---

## Tech Stack (PoC)

Possible implementation stack:

- Python
- LLM API (OpenAI / open-source model)
- arXiv / Semantic Scholar API
- PDF parser (PyMuPDF / pdfminer)
- SQLite (state & metadata)
- Vector embeddings (FAISS / Chroma)

---

## Project Goal

Demonstrate a **robust agentic system capable of orchestrating multiple tools and reasoning steps to produce a coherent literature review** under operational constraints and failure scenarios.