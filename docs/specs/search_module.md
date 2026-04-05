## Article retrieval

Sources:
- arXiv API
- OpenAlex API

First step for each search query is to retrieve articles and try to fill the fields as much as possible.

Second step is to deduplicate articles and consolidate (merge) them.

## Relevance assessment

Performed after each search query was send and a collection of articles was recieved.

First, again run deduplication (consolidation) pipeline just in case.

Second, mark articles with highest completeness (the more fields are not null the better, good citation format is appriciated as well).

Third, based on User Query and research directions set one of the following marks for each article:
- NOT_REL: the article is not relevant to the User Query and defined research directions.
- REL-: the article is somewhat related to User Query and defined research directions, yet it does not provide much.
- REL: the article is relevant to the User Query and defined research directions.
- REL+: the article is highly relevant and significant to User Query and defined research directions.

Finally, filter out NOT_REL articles, REL- articles that have bad completeness if their removal does not make article list empty.