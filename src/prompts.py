from jinja2 import Environment


env = Environment(autoescape=True)

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


PROMPT_RELEVANCE_FILTER = env.from_string("""
You are evaluating research papers for a literature review. Assign a relevance label to each paper.

Topic: {{topic}}

Research directions:
{% for direction in directions %}
- {{direction}}
{% endfor %}

Relevance labels:
- NOT_REL: not relevant to the topic and research directions at all
- REL-: tangentially related but provides little direct value for this literature review
- REL: clearly relevant and useful for this literature review
- REL+: highly relevant and significant; a key paper for this topic

Papers to evaluate (use the exact paper_id in your response):
{% for paper in papers %}
[{{paper.paper_id}}]
Title: {{paper.title}}
Abstract: {{paper.abstract}}

{% endfor %}

Return a relevance score for EVERY paper listed above. Use the exact paper_id values shown in brackets.
""")


PROMPT_ADDITIONAL_QUERIES = env.from_string("""
You are helping conduct a literature review. The current set of retrieved papers is insufficient — there are not enough highly relevant papers.

Topic: {{topic}}

Research directions:
{% for direction in directions %}
- {{direction}}
{% endfor %}

Papers found so far (with relevance grades):
{% for paper in papers %}
- [{{paper.relevance}}] {{paper.title}}
{% endfor %}

Search queries already used:
{% for q in previous_queries %}
- {{q}}
{% endfor %}

Generate 3-5 NEW search queries for arXiv that would find additional relevant papers. Focus on research directions that are underrepresented in the papers found so far. Do NOT repeat queries already used.

New search queries:
""")


PROMPT_SUMMARIZE_PAPER = env.from_string("""
Summarize the following research paper for use in a literature review. Extract the key information in four sections:

**Problem**: What specific problem or research question does this paper address?
**Method**: What approach, technique, or methodology is proposed or used?
**Results**: What are the main findings, contributions, or outcomes?
**Limitations**: What limitations, open questions, or future work are mentioned?

Keep each section to 2-3 concise, precise sentences. Use technical language appropriate for an academic audience.

Paper title: {{title}}

{% if full_text %}
Full paper text (excerpt):
{{full_text}}
{% else %}
Abstract:
{{abstract}}
{% endif %}

Summary:
""")


PROMPT_COMPOSE_REVIEW = env.from_string("""
User wants to make a literature review of a certain topic. Your task is to compose a review of the literature for a given topic, relevant research directions, and found papers.

Structure your review in a Markdown format. You need to cover the following aspects:
- Research directions
- Key papers
- Summary of approaches
- Open research problems
- Structured citations


Topic: {{topic}}

## Directions

{% for direction in directions %}
- {{direction}}
{% endfor %}

## Papers

{% for result in search_results %}
### {{result.title}}

Authors: {{result.authors}}

Relevance: {{result.relevance}}

Summary:
{{result.summary}}

DOI: {{result.doi}}

Citation: {{result.citation}}

{% endfor %}

You must start your review with <review> and end it with </review>.
""")
