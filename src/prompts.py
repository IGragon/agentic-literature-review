from jinja2 import Environment


# autoescape=True for prompts rendering plain user-supplied text (topic, titles)
env = Environment(autoescape=True)

# autoescape=False for LaTeX/BibTeX prompts - avoids HTML-escaping & in author names / keys
env_noesc = Environment(autoescape=False)


PROMPT_EXPAND_TOPIC = env.from_string("""
User wants to make a literature review of a certain topic. Your task is to construct a list of research directions that are relevant to the topic. The directions should be short and specific. List length must be from 1 when topic is specific and up to 5 when topic is general, interdisciplinary, or multi-directional.

Topic: {{topic}}

Directions:
""")


PROMPT_CONSTRUCT_SEARCH_QUERIES = env.from_string("""
User wants to make a literature review of a certain topic. Your task is to construct search queries for arXiv for a given topic and relevant research directions.

Topic: {{topic}}

Directions:
{% for direction in directions %}
- {{direction}}
{% endfor %}


Your output will be used to query arXiv via the arXiv API in the `query` parameter.

Search queries for arXiv:
""")


# ---------------------------------------------------------------------------
# Code-Act compose agent prompts
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = r"""You are an expert academic writer. Compose a LaTeX literature review and compile it to PDF using the tools available to you.

TOOLS (these are your only file access - you cannot read or write any other paths):
- write_bibliography(content): Write BibTeX entries to references.bib
- read_bibliography(): Read references.bib
- write_latex(content): Write the complete LaTeX document to review.tex
- read_latex(): Read review.tex
- compile(): Compile with latexmk (handles pdflatex + bibtex passes automatically).
  Returns "OK - PDF generated." on success or "ERROR:\n{trace}" on failure.

WORKFLOW:
1. Call write_bibliography() with the provided BibTeX content (write keys EXACTLY as given).
2. Call write_latex() with the complete LaTeX document.
3. Call compile(). If it returns "OK" you are DONE.
4. If it returns "ERROR": diagnose which file is the problem, read it, fix it, recompile.
   - BibTeX parse error or undefined entry -> read_bibliography(), rewrite the corrected .bib, compile()
   - LaTeX undefined command / bad environment -> read_latex(), fix the .tex, compile()
   - Unresolved \cite{key}: verify the key in \tex EXACTLY matches the key in .bib (case-sensitive)
5. Repeat step 4 until compile() returns "OK".

REQUIRED REVIEW STRUCTURE (sections in this order):
  \section{Introduction}
  \section{<direction 1 name>}
  ... one \section per research direction ...
  \section{Synthesis and Discussion}
  \section{Open Research Problems}
  \section{Conclusion}

RECOMMENDED PREAMBLE - copy verbatim, replace TOPIC_HERE with the escaped topic title:
\documentclass[12pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{geometry}
\usepackage[hidelinks]{hyperref}
\usepackage{cite}
\usepackage{parskip}
\geometry{margin=1in}
\title{\textbf{Literature Review:} TOPIC_HERE}
\author{Agentic Literature Review System}
\date{\today}
\begin{document}
\maketitle
\newpage
\tableofcontents
\newpage

DOCUMENT MUST END WITH EXACTLY:
\bibliographystyle{plain}
\bibliography{references}
\end{document}

CITATION RULES:
- In prose, cite papers with \cite{key}. Use ONLY the exact keys from the provided list.
- Every paper must be cited at least once somewhere in the body.
- Do NOT invent or modify citation keys."""


PROMPT_COMPOSE_AGENT_TASK = env_noesc.from_string("""Topic: {{ topic }}

Research directions to cover:
{% for d in directions %}
- {{ d }}
{% endfor %}

Available papers - cite using \\cite{key} with the exact keys below:
{% for p in papers %}
Key: {{ p.bibtex_key }}
Title: {{ p.title }}
Authors: {{ p.authors }}, {{ p.published_date }}
Abstract: {{ p.abstract }}
{% endfor %}

Write references.bib with EXACTLY this content (do not modify citation keys):
---
{{ bibliography }}
---
{% if feedback %}
REVISION REQUIRED - the previous version of this review was evaluated and rejected. You MUST address all of the following feedback:
{{ feedback }}
{% endif %}
Begin now. Call write_bibliography() first.
""")


# ---------------------------------------------------------------------------
# Evaluate-review prompt (unchanged from prior version)
# ---------------------------------------------------------------------------

PROMPT_EVALUATE_REVIEW = env_noesc.from_string("""
You are evaluating a LaTeX literature review for quality. Assess the review against established academic criteria.

Topic: {{ topic }}

Expected research directions ({{ directions | length }} total):
{% for direction in directions %}
- {{ direction }}
{% endfor %}

Review to evaluate:
---
{{ review }}
---

Evaluate using these 5 criteria (adapted from Boote & Beile 2005 and postgraduate literature review rubrics):

1. COVERAGE - Does the review have a dedicated \\section for each of the {{ directions | length }} expected research directions listed above?
2. SYNTHESIS - Does the review compare and contrast papers and approaches across the direction (not just summarize each paper individually in sequence)?
3. CITATIONS - Are papers cited using \\cite{} commands in the prose? (Papers should be referenced within arguments, not just appear in a list.)
4. STRUCTURE - Does the review have all of: Introduction, per-direction sections, Synthesis/Discussion section, Open Research Problems section, and Conclusion?
5. RESEARCH GAPS - Does the review identify open problems, limitations, or future research directions?

Decision rules:
- ACCEPTED: All 5 criteria are clearly met, OR exactly 4 are met with only minor issues in the 5th.
- NOT ACCEPTED: 2 or more criteria are not met or are substantially deficient.

If NOT ACCEPTED, provide specific and actionable feedback: name which criteria failed and exactly what needs to be added or fixed. Be concrete (e.g. "Direction X has no dedicated section", "Papers are listed but never compared").
If ACCEPTED, set feedback to an empty string.
""")
