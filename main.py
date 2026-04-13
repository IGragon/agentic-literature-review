import logging
import os
import time
import uuid

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

from src.agentic_workflow import (
    AgenticLiteratureReview,
    NoRelevantPapersFound,
    set_search_progress_callback,
    set_summarize_progress_callback,
)
from src.session_store import (
    delete_session,
    get_session_pdf_path,
    list_sessions,
    load_session,
    make_session,
    save_session,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

st.set_page_config(
    page_title="Agentic Literature Review",
    page_icon="📚",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "loaded_session_id" not in st.session_state:
    st.session_state.loaded_session_id = None
if "new_topic_mode" not in st.session_state:
    st.session_state.new_topic_mode = True
if "confirm_delete_id" not in st.session_state:
    st.session_state.confirm_delete_id = None

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
topic = ""
run_btn = False

with st.sidebar:
    st.title("Literature Review")
    st.caption("Agentic research assistant")
    st.divider()

    if st.session_state.new_topic_mode:
        topic = st.text_area(
            "Research topic",
            placeholder="e.g. Prompt injection attacks in LLM agents",
            height=120,
        )
        run_btn = st.button("▶ Run", type="primary", use_container_width=True, disabled=not topic.strip())
    else:
        if st.button("+ Research new topic", type="primary", use_container_width=True):
            st.session_state.new_topic_mode = True
            st.session_state.loaded_session_id = None
            st.rerun()

    st.divider()

    saved_sessions = list_sessions()
    if saved_sessions:
        st.caption("Previous runs")
        for s in saved_sessions:
            date_str = s.created_at[:10]
            if st.session_state.confirm_delete_id == s.id:
                st.caption(f'Delete "{s.name}"?')
                col_cancel, col_confirm = st.columns(2)
                with col_cancel:
                    if st.button("✕", key=f"cancel_{s.id}", use_container_width=True):
                        st.session_state.confirm_delete_id = None
                        st.rerun()
                with col_confirm:
                    if st.button("✓", key=f"confirm_{s.id}", use_container_width=True, type="primary"):
                        delete_session(s.id)
                        if st.session_state.loaded_session_id == s.id:
                            st.session_state.loaded_session_id = None
                        st.session_state.confirm_delete_id = None
                        st.rerun()
            else:
                col_btn, col_del = st.columns([5, 1], gap="small")
                with col_btn:
                    if st.button(f"{s.name}\n{date_str}", key=f"load_{s.id}", use_container_width=True):
                        st.session_state.loaded_session_id = s.id
                        st.session_state.new_topic_mode = False
                        st.rerun()
                with col_del:
                    if st.button("x", key=f"del_{s.id}", use_container_width=True):
                        st.session_state.confirm_delete_id = s.id
                        st.rerun()
    else:
        st.caption("No saved runs yet.")

    st.divider()
    st.caption("Typical runtime: 2-4 minutes.")
    st.caption("Searches arXiv, filters for relevance, and synthesizes results using an LLM.")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RELEVANCE_BADGE = {
    "REL+":    "🟢 REL+",
    "REL":     "🔵 REL",
    "REL-":    "🟡 REL-",
    "NOT_REL": "🔴 NOT_REL",
    "":        "",
}

NODE_TO_STEP = {
    "expand_topic":            "planning",
    "search":                  "search",
    "filter_relevance":        "filtering",
    "evaluate_quality":        "quality_eval",
    "form_additional_queries": "retry_search",
    "download_and_summarize":  "summarizing",
    "compose_review_latex":    "composing",
    "evaluate_review":         "review_eval",
}


def run_pipeline(t: str, session_id: str):
    alr = AgenticLiteratureReview(topic=t, session_id=session_id)
    for node_name, result in alr.run():
        step = NODE_TO_STEP.get(node_name)
        if step:
            yield step, result


def display_results(papers, review, footer, pdf_path=None, quality_warning=None):
    if quality_warning:
        st.warning(f"Quality notice: {quality_warning}")

    col_papers, col_review = st.columns([2, 3], gap="large")

    with col_papers:
        st.subheader("Retrieved papers")
        for p in papers:
            badge = _RELEVANCE_BADGE.get(p.get("relevance", ""), "")
            label = f"{badge}  {p['title']}" if badge else p["title"]
            with st.expander(label):
                st.caption(f"{p['authors']} · {p['published_date']}")
                if p.get("summary") and p["summary"] != p.get("abstract", ""):
                    st.markdown(p["summary"])
                else:
                    st.write(p["abstract"])
                st.link_button("View on arXiv / DOI", p["url"])
                if p.get("citation"):
                    with st.expander("BibTeX"):
                        st.code(p["citation"], language="bibtex")

    with col_review:
        st.subheader("Generated literature review")

        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            pdf_viewer(pdf_bytes, height=700)
            st.download_button(
                "Download review (.pdf)",
                data=pdf_bytes,
                file_name="literature_review.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            with st.expander("LaTeX source"):
                st.code(review, language="latex")

        st.download_button(
            "Download LaTeX source (.tex)",
            data=review,
            file_name="literature_review.tex",
            mime="text/x-tex",
            use_container_width=True,
        )

        st.divider()
        st.caption(footer)


def _open_search_status(steps_area, label: str, expanded: bool):
    status = steps_area.status(label, state="running", expanded=expanded)
    with status:
        progress_ph = st.empty()
    return status, progress_ph


def _register_search_progress(progress_ph):
    def _cb(current: int, total: int, query: str) -> None:
        if total > 0:
            progress_ph.progress(
                current / total,
                text=f"Query {current} / {total} - *{query[:90]}*",
            )
    set_search_progress_callback(_cb)


def _open_summarize_status(steps_area):
    status = steps_area.status("Downloading & summarizing papers...", state="running", expanded=True)
    with status:
        progress_ph = st.empty()
    return status, progress_ph


def _register_summarize_progress(progress_ph):
    def _cb(current: int, total: int, title: str) -> None:
        if total > 0:
            progress_ph.progress(
                current / total,
                text=f"Paper {current} / {total} - *{title[:80]}*",
            )
    set_summarize_progress_callback(_cb)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.title("Agentic Literature Review Generator")

if run_btn:
    start = time.time()
    session_id = str(uuid.uuid4())
    steps_area = st.container()
    statuses = {}
    statuses["planning"] = steps_area.status("Expanding topic...", state="running", expanded=True)

    directions_saved = None
    papers_saved = None
    review_saved = None
    review_pdf_path_saved = None
    quality_warning_saved = None
    search_count = 0
    compose_count = 0
    compose_status = None
    eval_status = None
    _search_progress_ph = None
    _summ_progress_ph = None

    try:
        for step_key, result in run_pipeline(topic, session_id=session_id):

            if step_key == "planning":
                directions_saved = result["directions"]
                with statuses["planning"]:
                    for i, d in enumerate(directions_saved, 1):
                        st.markdown(f"**{i}.** {d}")
                statuses["planning"].update(
                    label=f"Topic planning - {len(directions_saved)} directions",
                    state="complete",
                    expanded=False,
                )
                statuses["search"], _search_progress_ph = _open_search_status(
                    steps_area, "Searching arXiv and OpenAlex...", expanded=True
                )
                _register_search_progress(_search_progress_ph)
                search_count = 1

            elif step_key == "search":
                set_search_progress_callback(None)
                papers_saved = result.get("search_results") or []
                statuses["search"].update(
                    label=f"Paper search (iteration {search_count}) - {len(papers_saved)} papers",
                    state="complete",
                    expanded=False,
                )
                statuses["filtering"] = steps_area.status("Filtering for relevance...", state="running", expanded=False)

            elif step_key == "filtering":
                papers_saved = result.get("search_results") or []
                rel_plus = sum(1 for p in papers_saved if p.get("relevance") == "REL+")
                rel = sum(1 for p in papers_saved if p.get("relevance") == "REL")
                rel_minus = sum(1 for p in papers_saved if p.get("relevance") == "REL-")
                statuses["filtering"].update(
                    label=f"Relevance filtering - {len(papers_saved)} papers kept (REL+:{rel_plus} REL:{rel} REL-:{rel_minus})",
                    state="complete",
                    expanded=False,
                )
                statuses["quality_eval"] = steps_area.status("Evaluating coverage...", state="running", expanded=False)

            elif step_key == "quality_eval":
                quality_warning_saved = result.get("quality_warning")
                quality_ok = result.get("quality_ok")
                if quality_ok:
                    statuses["quality_eval"].update(
                        label="Coverage evaluation - quality OK",
                        state="complete",
                        expanded=False,
                    )
                    statuses["summarizing"], _summ_progress_ph = _open_summarize_status(steps_area)
                    _register_summarize_progress(_summ_progress_ph)
                else:
                    statuses["quality_eval"].update(
                        label="Coverage evaluation - insufficient, retrying...",
                        state="complete",
                        expanded=False,
                    )

            elif step_key == "retry_search":
                search_count += 1
                statuses["search"], _search_progress_ph = _open_search_status(
                    steps_area,
                    f"Searching for more papers (iteration {search_count})...",
                    expanded=True,
                )
                _register_search_progress(_search_progress_ph)

            elif step_key == "summarizing":
                set_summarize_progress_callback(None)
                papers_saved = result.get("search_results") or []
                statuses["summarizing"].update(
                    label=f"Summarization - {len(papers_saved)} papers summarized",
                    state="complete",
                    expanded=False,
                )
                compose_status = steps_area.status("Composing LaTeX review...", state="running", expanded=False)

            elif step_key == "composing":
                compose_count += 1
                review_saved = result.get("review")
                review_pdf_path_saved = result.get("review_pdf_path")
                if compose_count > 1:
                    compose_status.update(
                        label=f"Composing LaTeX review (refinement {compose_count})...",
                        state="running",
                        expanded=False,
                    )
                if eval_status:
                    eval_status.update(
                        label="Review evaluation - refining...",
                        state="complete",
                        expanded=False,
                    )
                    eval_status = None

            elif step_key == "review_eval":
                accepted = result.get("review_accepted")
                if accepted:
                    compose_status.update(
                        label=f"Review composition complete ({compose_count} attempt(s))",
                        state="complete",
                        expanded=False,
                    )
                else:
                    eval_status = steps_area.status(
                        "Evaluating review quality...", state="running", expanded=False
                    )

        elapsed = time.time() - start
        st.success(f"Pipeline complete in {elapsed:.0f}s.")

        if directions_saved and papers_saved and review_saved:
            word_count = len(review_saved.split())
            footer = f"Generated in {elapsed:.0f}s - {word_count} words - {len(papers_saved)} papers"
            display_results(
                papers_saved, review_saved, footer,
                pdf_path=review_pdf_path_saved,
                quality_warning=quality_warning_saved,
            )

            session = make_session(
                topic, directions_saved, papers_saved, review_saved,
                session_id=session_id,
                quality_warning=quality_warning_saved,
            )
            save_session(session)
            st.session_state.loaded_session_id = session.id
            st.session_state.new_topic_mode = False
            st.rerun()

    except NoRelevantPapersFound as e:
        for s in statuses.values():
            try:
                s.update(state="error")
            except Exception:
                pass
        st.error(f"No relevant papers found: {e}")
        logging.exception("No papers found")

    except Exception as e:
        for s in statuses.values():
            try:
                s.update(state="error")
            except Exception:
                pass
        if compose_status:
            try:
                compose_status.update(state="error")
            except Exception:
                pass
        st.error(f"Pipeline failed: {e}")
        logging.exception("Pipeline error")

elif st.session_state.loaded_session_id:
    try:
        session = load_session(st.session_state.loaded_session_id)
        date_str = session.created_at[:16].replace("T", " ")
        st.info(f"Saved run: **{session.name}** ({date_str})")
        word_count = len(session.review.split())
        footer = f"{word_count} words - {len(session.search_results)} papers - saved {date_str}"
        pdf_path = get_session_pdf_path(session.id)
        display_results(
            session.search_results,
            session.review,
            footer,
            pdf_path=pdf_path,
            quality_warning=getattr(session, "quality_warning", None),
        )
    except Exception as e:
        st.error(f"Failed to load session: {e}")
        st.session_state.loaded_session_id = None

else:
    st.info("Enter a research topic in the sidebar and click **▶ Run** to start.")
    st.stop()
