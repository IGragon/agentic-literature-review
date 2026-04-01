import logging
import time

import streamlit as st

from src.agentic_workflow import AgenticLiteratureReview
from src.session_store import delete_session, list_sessions, load_session, make_session, save_session

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
    st.caption("Typical runtime: 60-90 seconds.")
    st.caption("Searches arXiv and synthesizes results using an LLM.")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
NODE_TO_STEP = {
    "expand_topic": "planning",
    "search": "search",
    "compose_review": "composing",
}


def run_pipeline(t):
    alr = AgenticLiteratureReview(topic=t)
    for node_name, result in alr.run():
        step = NODE_TO_STEP.get(node_name)
        if step:
            yield step, result


def display_results(papers, review, footer):
    col_papers, col_review = st.columns([2, 3], gap="large")

    with col_papers:
        st.subheader("Retrieved papers")
        for p in papers:
            with st.expander(p["title"]):
                st.caption(f"{p['authors']} · {p['published_date']}")
                st.write(p["abstract"])
                st.link_button("View on arXiv", p["url"])
                if p.get("citation"):
                    with st.expander("BibTeX"):
                        st.code(p["citation"], language="bibtex")

    with col_review:
        st.subheader("Generated literature review")
        st.markdown(review)
        st.divider()
        st.caption(footer)
        st.download_button(
            "Download review (.md)",
            data=review,
            file_name="literature_review.md",
            mime="text/markdown",
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.title("Agentic Literature Review Generator")

if run_btn:
    start = time.time()
    steps_area = st.container()
    statuses = {}
    statuses["planning"] = steps_area.status("Expanding topic...", state="running", expanded=True)

    directions_saved = None
    papers_saved = None
    review_saved = None

    try:
        for step_key, result in run_pipeline(topic):

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
                statuses["search"] = steps_area.status("Searching arXiv...", state="running", expanded=True)

            elif step_key == "search":
                papers_saved = result["search_results"]
                with statuses["search"]:
                    st.caption(f"Retrieved {len(papers_saved)} papers.")
                statuses["search"].update(
                    label=f"Paper search - {len(papers_saved)} papers retrieved",
                    state="complete",
                    expanded=False,
                )
                statuses["composing"] = steps_area.status("Composing review...", state="running", expanded=True)

            elif step_key == "composing":
                review_saved = result["review"]
                elapsed = time.time() - start
                statuses["composing"].update(
                    label="Review composition - complete",
                    state="complete",
                    expanded=False,
                )
                word_count = len(review_saved.split())
                footer = f"Generated in {elapsed:.0f}s - {word_count} words - {len(papers_saved)} papers"
                display_results(papers_saved, review_saved, footer)

        st.success(f"Pipeline complete in {time.time() - start:.0f}s.")

        if directions_saved and papers_saved and review_saved:
            session = make_session(topic, directions_saved, papers_saved, review_saved)
            save_session(session)
            st.session_state.loaded_session_id = session.id
            st.session_state.new_topic_mode = False
            st.rerun()

    except Exception as e:
        for s in statuses.values():
            try:
                s.update(state="error")
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
        display_results(session.search_results, session.review, footer)
    except Exception as e:
        st.error(f"Failed to load session: {e}")
        st.session_state.loaded_session_id = None

else:
    st.info("Enter a research topic in the sidebar and click **▶ Run** to start.")
    st.stop()
