## Literature Review Agentic Workflow

User Query

↓

Step 1: Expand user query and fomulate 3-5 specific research directions that would be relevant in literature review for User Query.

↓

Step 2: For each of research directions generate 3-5 search queries to send to arXiv API or OpenAlex API

↓

Step 3: Send search requests and gather all the articles recieved

↓

Step 4: Perform relevance filtering

↓

Step 5: Evaluate if the retrieved articles are good enough. If yes, then procceed to Step 6. If not, then make more queries that would fulfill the article list and go to Step 3. If after N iterations there are zero articles, then we fail the workflow with "articles not found". If after N iterations we did not get good enough articles, then we may prompt a user to continue or mark the review as of "potentially low quality".

↓

Step 6: Summarize relevant articles from full text to use in a review.

↓

Step 7: Compose review based on User Query, defined research directions, and summaries of retrieved articles. 

↓

Step 8: Check if the review is good enough. If not, then go to Step 7 with additional feedback (maxinum of N times). If yes, then accept the review and give a response to a user.

↓

Finish Run
