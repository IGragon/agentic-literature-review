## Observability

LangFuse is used as an observability platform to track workflow flow:
- Session: starts at user query and ends with recieved output
- Trace: starts at LLM/Agent recieving control
- Span: step inside a trace
- Event: tool-call or api usage

## Evals

### Static benchmark

From known articles we take introduction and prior work sections.

Construct a dataset with the samples containing the following components:
- Article name: that would be used as an input for the pipeline
- Mentioned articles: a collection of research papers cited by corresponding article

There we measure Recall and Precision of articles retrieved by workflow (before and after relevance filtering).

### End-to-End assessment

For end-to-end assessment DeepEval is used to evaluate the resulting article based on provided "grading criteria" that assesses language, formatting, soundness. (TBD when real prompt for DeepEval will be composed)

As inputs we use a list of topics for literature review.

There we measure average grade
