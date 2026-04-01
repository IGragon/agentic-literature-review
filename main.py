import logging
import time

import streamlit as st

from src.agentic_workflow import AgenticLiteratureReview

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

st.set_page_config(
    page_title="Agentic Literature Review",
    page_icon="📚",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Literature Review")
    st.caption("Agentic research assistant")
    st.divider()

    topic = st.text_area(
        "Research topic",
        placeholder="e.g. Prompt injection attacks in LLM agents",
        height=120,
    )

    run_btn = st.button("▶ Run", type="primary", use_container_width=True, disabled=not topic.strip())

    st.divider()
    st.caption("Typical runtime: 60-90 seconds.")
    st.caption("Searches arXiv and synthesizes results using an LLM.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.title("Agentic Literature Review Generator")

if not run_btn:
    st.info("Enter a research topic in the sidebar and click **▶ Run** to start.")
    st.stop()

NODE_TO_STEP = {
    "expand_topic": "planning",
    "search": "search",
    "compose_review": "composing",
}


def run_pipeline(topic):
    alr = AgenticLiteratureReview(topic=topic)
    for node_name, result in alr.run():
        step = NODE_TO_STEP.get(node_name)
        if step:
            yield step, result


start = time.time()

# Steps render in this container so they appear above the two-column area.
steps_area = st.container()
col_papers, col_review = st.columns([2, 3], gap="large")

statuses = {}
statuses["planning"] = steps_area.status("Expanding topic...", state="running", expanded=True)

paper_count = 0

try:
    for step_key, result in run_pipeline(topic):

        if step_key == "planning":
            directions = result["directions"]
            with statuses["planning"]:
                for i, d in enumerate(directions, 1):
                    st.markdown(f"**{i}.** {d}")
            statuses["planning"].update(
                label=f"Topic planning - {len(directions)} directions",
                state="complete",
                expanded=False,
            )
            statuses["search"] = steps_area.status("Searching arXiv...", state="running", expanded=True)

        elif step_key == "search":
            papers = result["search_results"]
            paper_count = len(papers)
            with statuses["search"]:
                st.caption(f"Retrieved {paper_count} papers.")
            statuses["search"].update(
                label=f"Paper search - {paper_count} papers retrieved",
                state="complete",
                expanded=False,
            )

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

            statuses["composing"] = steps_area.status("Composing review...", state="running", expanded=True)

        elif step_key == "composing":
            review = result["review"]
            elapsed = time.time() - start
            statuses["composing"].update(
                label="Review composition - complete",
                state="complete",
                expanded=False,
            )

            with col_review:
                st.subheader("Generated literature review")
                st.markdown(review)
                st.divider()
                word_count = len(review.split())
                st.caption(f"Generated in {elapsed:.0f}s - {word_count} words - {paper_count} papers")
                st.download_button(
                    "Download review (.md)",
                    data=review,
                    file_name="literature_review.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

    st.success(f"Pipeline complete in {time.time() - start:.0f}s.")

except Exception as e:
    for s in statuses.values():
        try:
            s.update(state="error")
        except Exception:
            pass
    st.error(f"Pipeline failed: {e}")
    logging.exception("Pipeline error")
