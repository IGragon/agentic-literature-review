import streamlit as st
from src.agentic_workflow import AgenticLiteratureReview

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Agentic Literature Review",
    page_icon="📚",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar — inputs & pipeline status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📚 Literature Review")
    st.caption("Agentic research assistant")

    st.divider()

    topic = st.text_area(
        "Research topic",
        placeholder="e.g. Prompt injection attacks in LLM agents",
        height=100,
    )

    # with st.expander("Advanced settings", expanded=False):
    #     max_papers = st.slider("Max papers", min_value=5, max_value=20, value=10)
    #     max_iterations = st.slider("Max search iterations", min_value=1, max_value=3, value=2)

    run_btn = st.button("▶ Run", type="primary", disabled=not topic.strip())

    st.divider()

    st.subheader("Pipeline status")
    status_placeholder = st.empty()

# ---------------------------------------------------------------------------
# Pipeline steps definition
# ---------------------------------------------------------------------------
STEPS = [
    ("planning", "Topic planning"),
    ("search", "Paper search"),
    # ("filtering",    "Relevance filtering"),
    # ("downloading",  "PDF download"),
    # ("summarizing",  "Summarization"),
    ("composing", "Review composition"),
]

ICONS = {"pending": "⬜", "running": "🔄", "done": "✅", "error": "❌"}


def render_status(step_states: dict) -> str:
    lines = []
    for key, label in STEPS:
        icon = ICONS[step_states.get(key, "pending")]
        lines.append(f"{icon} {label}")
    return "\n".join(lines)


def pipeline(topic, **kwargs):
    agentic_literature_review = AgenticLiteratureReview(
        topic=topic,
    )
    for node_name, results in agentic_literature_review.run():
        match node_name:
            case "expand_topic":
                yield "planning", results
            case "search":
                yield "search", results
            case "compose_review":
                yield "composing", results
    return []


# ---------------------------------------------------------------------------
# Main content — rendered progressively on Run
# ---------------------------------------------------------------------------
st.title("Agentic Literature Review Generator")

if not run_btn:
    st.info("Enter a research topic in the sidebar and click **▶ Run** to start.")
    st.stop()

# Initialise step states
step_states = {key: "pending" for key, _ in STEPS}
status_placeholder.text(render_status(step_states))

results: dict = {}

for step_key, result in pipeline(topic):
    step_states[step_key] = "done"
    results[step_key] = result
    status_placeholder.text(render_status(step_states))

    # ---- Research directions ----
    if step_key == "planning":
        st.subheader("🗺️ Research directions")
        for i, d in enumerate(result["directions"], 1):
            st.markdown(f"**{i}.** {d}")

    # ---- Retrieved papers ----
    elif step_key == "search":
        st.subheader("🔍 Retrieved papers")
        for p in result["search_results"]:
            st.markdown(
                f"- [{p['title']}]({p['url']}) — {p['authors']} ({p['published_date']})*"
            )

    # # ---- Filtered papers ----
    # elif step_key == "filtering":
    #     st.subheader("✅ After relevance filtering")
    #     rows = [
    #         {"Title": p["title"], "Authors": p["authors"], "Year": p["year"],
    #          "Relevance": f"{p['score']:.2f}", "URL": p["url"]}
    #         for p in result["papers"]
    #     ]
    #     st.dataframe(rows, width="stretch")

    # # ---- Summaries ----
    # elif step_key == "summarizing":
    #     st.subheader("📝 Paper summaries")
    #     for s in result["summaries"]:
    #         with st.expander(s["title"]):
    #             col1, col2 = st.columns(2)
    #             with col1:
    #                 st.markdown(f"**Problem:** {s['problem']}")
    #                 st.markdown(f"**Method:** {s['method']}")
    #             with col2:
    #                 st.markdown(f"**Results:** {s['results']}")
    #                 st.markdown(f"**Limitations:** {s['limitations']}")

    # ---- Literature review ----
    elif step_key == "composing":
        st.subheader("📄 Generated literature review")
        st.markdown(result["review"])
        st.download_button(
            "⬇ Download review (.md)",
            data=result["review"],
            file_name="literature_review.md",
            mime="text/markdown",
        )

st.success("Pipeline complete.")
