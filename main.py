import time
import streamlit as st

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

    with st.expander("Advanced settings", expanded=False):
        max_papers = st.slider("Max papers", min_value=5, max_value=20, value=10)
        max_iterations = st.slider("Max search iterations", min_value=1, max_value=3, value=2)

    run_btn = st.button("▶ Run", type="primary", disabled=not topic.strip())

    st.divider()

    st.subheader("Pipeline status")
    status_placeholder = st.empty()

# ---------------------------------------------------------------------------
# Pipeline steps definition
# ---------------------------------------------------------------------------
STEPS = [
    ("planning",     "Topic planning"),
    ("search",       "Paper search"),
    ("filtering",    "Relevance filtering"),
    ("downloading",  "PDF download"),
    ("summarizing",  "Summarization"),
    ("composing",    "Review composition"),
]

ICONS = {"pending": "⬜", "running": "🔄", "done": "✅", "error": "❌"}


def render_status(step_states: dict) -> str:
    lines = []
    for key, label in STEPS:
        icon = ICONS[step_states.get(key, "pending")]
        lines.append(f"{icon} {label}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Placeholder state for demo / stub pipeline
# ---------------------------------------------------------------------------
def stub_pipeline(_topic: str, _max_papers: int, _max_iterations: int):
    """
    Yields (step_key, partial_result) tuples as each step completes.
    Replace with real agent calls.
    """
    # Step 1 — Topic planning
    yield "planning", {
        "directions": [
            "Adversarial prompt attacks on LLM tool-use",
            "Jailbreaking and instruction-following robustness",
            "RAG pipeline injection vectors",
            "Defense mechanisms and sandboxing",
        ]
    }
    time.sleep(0.5)

    # Step 2 — Paper search
    yield "search", {
        "papers": [
            {"title": "Prompt Injection Attacks and Defenses in LLM-Integrated Applications",
             "authors": "Liu et al.", "year": 2023, "url": "https://arxiv.org/abs/2310.12815",
             "source": "arXiv"},
            {"title": "Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications",
             "authors": "Greshake et al.", "year": 2023, "url": "https://arxiv.org/abs/2302.12173",
             "source": "arXiv"},
            {"title": "Baseline Defenses for Adversarial Attacks Against Aligned Language Models",
             "authors": "Jain et al.", "year": 2023, "url": "https://arxiv.org/abs/2309.00614",
             "source": "Semantic Scholar"},
        ]
    }
    time.sleep(0.5)

    # Step 3 — Relevance filtering
    yield "filtering", {
        "papers": [
            {"title": "Prompt Injection Attacks and Defenses in LLM-Integrated Applications",
             "authors": "Liu et al.", "year": 2023, "url": "https://arxiv.org/abs/2310.12815",
             "score": 0.94},
            {"title": "Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications",
             "authors": "Greshake et al.", "year": 2023, "url": "https://arxiv.org/abs/2302.12173",
             "score": 0.91},
        ]
    }
    time.sleep(0.5)

    # Step 4 — PDF download (no UI output, just status)
    yield "downloading", {}
    time.sleep(0.5)

    # Step 5 — Summarization
    yield "summarizing", {
        "summaries": [
            {
                "title": "Prompt Injection Attacks and Defenses in LLM-Integrated Applications",
                "problem": "LLM agents are vulnerable to adversarial instructions injected via external data sources.",
                "method": "Systematic taxonomy of injection attack vectors with empirical evaluation on real applications.",
                "results": "Most current LLM integrations are susceptible; proposed defenses reduce attack success by 60–80%.",
                "limitations": "Evaluation limited to a fixed set of applications; adaptive attacks not fully explored.",
            },
            {
                "title": "Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications",
                "problem": "Real-world LLM pipelines can be hijacked by injected instructions in retrieved documents.",
                "method": "Black-box attacks on deployed systems including Bing Chat and code assistants.",
                "results": "Demonstrated data exfiltration and unauthorized actions in production systems.",
                "limitations": "Responsible disclosure limits full reproducibility details.",
            },
        ]
    }
    time.sleep(0.5)

    # Step 6 — Review composition
    yield "composing", {
        "review": """## Literature Review: Prompt Injection Attacks in LLM Agents

### Introduction

Prompt injection has emerged as a critical security challenge for LLM-integrated systems.
As agents increasingly rely on external data sources, adversarial instructions embedded
in retrieved content can redirect agent behavior in unintended ways.

### Research Directions

Research in this area spans four main directions: (1) attack taxonomy and empirical
evaluation, (2) real-world exploitation of deployed systems, (3) robustness of aligned
models, and (4) defensive countermeasures.

### Key Works

**Liu et al. (2023)** provide a systematic taxonomy of prompt injection vectors in
LLM-integrated applications, demonstrating that most current pipelines lack adequate
defenses [1].

**Greshake et al. (2023)** demonstrate real-world exploitation of deployed LLM systems
including indirect prompt injection via web content, enabling data exfiltration and
unauthorized tool invocations [2].

### Open Problems

- Adaptive attacks against known defenses remain underexplored.
- Formal security guarantees for agentic pipelines are lacking.
- Evaluation benchmarks for injection robustness are nascent.

### References

[1] Liu et al., "Prompt Injection Attacks and Defenses in LLM-Integrated Applications," 2023.
[2] Greshake et al., "Not What You've Signed Up For," 2023.
"""
    }


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

for step_key, result in stub_pipeline(topic, max_papers, max_iterations):
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
        for p in result["papers"]:
            st.markdown(f"- [{p['title']}]({p['url']}) — {p['authors']} ({p['year']}) · *{p['source']}*")

    # ---- Filtered papers ----
    elif step_key == "filtering":
        st.subheader("✅ After relevance filtering")
        rows = [
            {"Title": p["title"], "Authors": p["authors"], "Year": p["year"],
             "Relevance": f"{p['score']:.2f}", "URL": p["url"]}
            for p in result["papers"]
        ]
        st.dataframe(rows, width="stretch")

    # ---- Summaries ----
    elif step_key == "summarizing":
        st.subheader("📝 Paper summaries")
        for s in result["summaries"]:
            with st.expander(s["title"]):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Problem:** {s['problem']}")
                    st.markdown(f"**Method:** {s['method']}")
                with col2:
                    st.markdown(f"**Results:** {s['results']}")
                    st.markdown(f"**Limitations:** {s['limitations']}")

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
