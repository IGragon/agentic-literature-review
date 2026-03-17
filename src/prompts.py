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

## Search results

{% for result in search_results %}
### {{result.title}}

Authors: {{result.authors}}

Abstract:
{{result.abstract}}

Summary:
{{result.summary}}
                               
DOI: {{result.doi}}

Citation: {{result.citation}}

{% endfor %}

You must start your review with <review> and end it with </review>.
""")
