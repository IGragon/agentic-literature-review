"""LangFuse observability integration for the literature review pipeline."""

import os
import threading
from typing import Any

from dotenv import load_dotenv
from langfuse import Langfuse
from langfuse.types import TraceContext

load_dotenv()

_langfuse_client: Langfuse | None = None
_tls = threading.local()


def get_client() -> Langfuse:
    global _langfuse_client
    if _langfuse_client is None:
        _langfuse_client = Langfuse()
    return _langfuse_client


def is_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_SECRET_KEY"))


def start_session(topic: str, session_id: str) -> str | None:
    """Start a pipeline session trace. Returns trace ID or None if disabled."""
    if not is_enabled():
        return None
    lf = get_client()
    chain = lf.start_observation(
        name="literature_review_pipeline",
        as_type="chain",
        input={"topic": topic},
        metadata={"session_id": session_id},
    )
    _tls.session_chain = chain
    _tls.trace_context = TraceContext(trace_id=chain.trace_id, parent_span_id=chain.id)
    _tls.span_stack = []
    return chain.trace_id


def end_session(output: dict | None = None) -> None:
    """End the pipeline session trace and flush data."""
    chain = getattr(_tls, "session_chain", None)
    if chain is None:
        return
    if output:
        chain.update(output=output)
    chain.end()
    _tls.session_chain = None
    _tls.trace_context = None
    _tls.span_stack = []
    get_client().flush()


def _current_trace_context() -> TraceContext | None:
    return getattr(_tls, "trace_context", None)


def start_span(name: str, input_data: Any = None) -> Any:
    """Start a span under the current trace. Returns span or None if disabled."""
    ctx = _current_trace_context()
    if ctx is None:
        return None
    lf = get_client()
    span = lf.start_observation(
        name=name,
        as_type="span",
        trace_context=ctx,
        input=_truncate(input_data),
    )
    _tls.trace_context = TraceContext(trace_id=span.trace_id, parent_span_id=span.id)
    stack = getattr(_tls, "span_stack", [])
    stack.append(span)
    _tls.span_stack = stack
    return span


def end_span(span: Any, output: Any = None) -> None:
    """End a span and restore the previous parent context."""
    if span is None:
        return
    if output is not None:
        span.update(output=_truncate(output))
    span.end()
    stack = getattr(_tls, "span_stack", [])
    if stack and stack[-1] is span:
        stack.pop()
        if stack:
            parent = stack[-1]
            _tls.trace_context = TraceContext(trace_id=parent.trace_id, parent_span_id=parent.id)
        else:
            chain = getattr(_tls, "session_chain", None)
            if chain:
                _tls.trace_context = TraceContext(trace_id=chain.trace_id, parent_span_id=chain.id)
            else:
                _tls.trace_context = None
    _tls.span_stack = stack


def traced_invoke(llm: Any, prompt: Any, name: str = "llm_call") -> Any:
    """Invoke an LLM and trace the call as a generation in LangFuse."""
    ctx = _current_trace_context()
    if ctx is None:
        return llm.invoke(prompt)

    model = os.getenv("OPENROUTER_MODEL", "unknown")
    lf = get_client()
    gen = lf.start_observation(
        name=name,
        as_type="generation",
        trace_context=ctx,
        model=model,
        input=_truncate(prompt),
    )
    try:
        result = llm.invoke(prompt)
        output = result.content if hasattr(result, "content") else str(result)
        gen.update(output=_truncate(output))
        usage = _extract_usage(result)
        if usage:
            gen.update(usage_details=usage)
        return result
    except Exception as e:
        gen.update(level="ERROR", status_message=str(e)[:500])
        raise
    finally:
        gen.end()


def log_event(name: str, input_data: Any = None, output: Any = None,
              metadata: dict | None = None) -> None:
    """Log a discrete event (tool call, API usage) under the current span."""
    ctx = _current_trace_context()
    if ctx is None:
        return
    lf = get_client()
    lf.create_event(
        name=name,
        trace_context=ctx,
        input=_truncate(input_data),
        output=_truncate(output),
        metadata=metadata,
    )


def _truncate(value: Any, max_len: int = 4000) -> Any:
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "...[truncated]"
    return value


def _extract_usage(result: Any) -> dict | None:
    meta = getattr(result, "usage_metadata", None)
    if not meta:
        return None
    return {
        "prompt_tokens": meta.get("prompt_tokens", 0),
        "completion_tokens": meta.get("completion_tokens", 0),
        "total_tokens": meta.get("total_tokens", 0),
    }
