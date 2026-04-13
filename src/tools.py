import os
import subprocess

from langchain_core.tools import tool as lc_tool


# ---------------------------------------------------------------------------
# Low-level helpers (used by compile_latex wrapper and make_latex_tools)
# ---------------------------------------------------------------------------

def write_latex(content: str, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def read_latex(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_bibliography(bibtex: str, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(bibtex)


def read_bibliography(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _run_latexmk(tex_path: str) -> dict:
    """Run latexmk on tex_path (handles pdflatex + bibtex passes).

    Returns {"status": "OK"} on success or {"status": "ERROR", "trace": str} on failure.
    Expects references.bib to exist in the same directory as tex_path.
    """
    dir_path = os.path.dirname(tex_path)
    tex_name = os.path.basename(tex_path)

    try:
        result = subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", tex_name],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=dir_path,
        )
    except subprocess.TimeoutExpired:
        return {"status": "ERROR", "trace": "latexmk timed out after 120s"}
    except Exception as exc:
        return {"status": "ERROR", "trace": str(exc)}

    if result.returncode == 0:
        return {"status": "OK"}

    # Extract error lines from log file (more structured than stdout)
    log_path = os.path.join(dir_path, tex_name.replace(".tex", ".log"))
    trace = ""
    if os.path.exists(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as f:
            log_lines = f.readlines()
        error_lines = [l.rstrip() for l in log_lines if l.startswith("!") or l.startswith("l.")]
        trace = "\n".join(error_lines[:80])

    if not trace:
        trace = result.stdout[-3000:] if result.stdout else result.stderr[-3000:]

    return {"status": "ERROR", "trace": trace}


def compile_latex(tex_path: str) -> dict:
    """Public wrapper around _run_latexmk. Used in tests and direct calls."""
    return _run_latexmk(tex_path)


# ---------------------------------------------------------------------------
# LangChain tool factory for Code-Act compose agent
# ---------------------------------------------------------------------------

def make_latex_tools(session_dir: str) -> list:
    """Return 5 LangChain tools scoped to session_dir.

    The agent never sees file paths - all operations are restricted to session_dir.
    Tools with no required input use `dummy: str = ""` to guarantee a valid JSON Schema
    for all OpenRouter models.
    """

    @lc_tool
    def write_bibliography(content: str) -> str:
        """Write BibTeX entries to references.bib.
        Call this first before write_latex or compile."""
        path = os.path.join(session_dir, "references.bib")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to references.bib."

    @lc_tool
    def read_bibliography(dummy: str = "") -> str:
        """Read the current content of references.bib.
        Use this to inspect and diagnose BibTeX errors before fixing."""
        path = os.path.join(session_dir, "references.bib")
        if not os.path.exists(path):
            return "(references.bib does not exist yet)"
        with open(path, encoding="utf-8") as f:
            return f.read()

    @lc_tool
    def write_latex(content: str) -> str:
        """Write the complete LaTeX document to review.tex.
        Must include \\documentclass, preamble, body, and \\end{document}."""
        path = os.path.join(session_dir, "review.tex")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to review.tex."

    @lc_tool
    def read_latex(dummy: str = "") -> str:
        """Read the current content of review.tex.
        Use this to inspect and diagnose LaTeX errors before fixing."""
        path = os.path.join(session_dir, "review.tex")
        if not os.path.exists(path):
            return "(review.tex does not exist yet)"
        with open(path, encoding="utf-8") as f:
            return f.read()

    @lc_tool
    def compile(dummy: str = "") -> str:
        """Compile review.tex using latexmk (handles pdflatex + bibtex passes).
        Returns 'OK - PDF generated.' on success.
        Returns 'ERROR:\\n{trace}' on failure - read the relevant file to diagnose."""
        tex_path = os.path.join(session_dir, "review.tex")
        if not os.path.exists(tex_path):
            return "ERROR: review.tex does not exist. Call write_latex() first."
        result = _run_latexmk(tex_path)
        if result["status"] == "OK":
            return "OK - PDF generated."
        return f"ERROR:\n{result['trace']}"

    return [write_bibliography, read_bibliography, write_latex, read_latex, compile]
