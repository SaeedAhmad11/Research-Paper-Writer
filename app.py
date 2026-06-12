"""
Research Paper Writer — Streamlit app.

Takes a Research Gap Report (markdown, produced by the gap-finder agent),
ranks the gaps, and writes a full research paper on the strongest gap
using the Groq API.

Run:  streamlit run app.py
Requires:  pip install streamlit groq
"""

import re
import datetime
from dataclasses import dataclass, field
from pathlib import Path

import streamlit as st

try:
    from groq import Groq
except ImportError:
    Groq = None

FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "moonshotai/kimi-k2-instruct",
]


@st.cache_data(show_spinner=False)
def list_groq_models(key: str):
    """Fetch chat models available to this API key; fall back to a static list."""
    try:
        models = [m.id for m in Groq(api_key=key).models.list().data]
        # filter out non-text models (whisper/tts/guard)
        bad = ("whisper", "tts", "guard", "orpheus")
        models = sorted(m for m in models if not any(b in m.lower() for b in bad))
        return models or FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS

# ----------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------

CONF_SCORE = {"high": 3, "medium": 2, "low": 1}
CATEGORY_WEIGHT = {
    "method-transfer gaps": 1.0,
    "orphaned future work": 0.8,
}


@dataclass
class Gap:
    title: str
    category: str
    confidence: str = "low"
    reasoning: str = ""
    evidence: list = field(default_factory=list)

    @property
    def score(self) -> float:
        base = CONF_SCORE.get(self.confidence.lower(), 1)
        cat = CATEGORY_WEIGHT.get(self.category.lower(), 0.9)
        return base * cat + 0.2 * len(self.evidence)


@dataclass
class Report:
    topic: str = ""
    summary: str = ""
    papers: list = field(default_factory=list)      # dicts: title, authors, year, citations, url
    paper_summaries: list = field(default_factory=list)
    gaps: list = field(default_factory=list)


def parse_report(text: str) -> Report:
    rep = Report()

    m = re.search(r"^#\s*Research Gap Report:\s*(.+)$", text, re.M)
    rep.topic = m.group(1).strip() if m else "Unknown topic"

    m = re.search(r"## Executive Summary\s*\n+(.*?)(?=\n## )", text, re.S)
    rep.summary = m.group(1).strip() if m else ""

    # Papers table
    for row in re.findall(r"^\|\s*\d+\s*\|(.+)$", text, re.M):
        cols = [c.strip() for c in row.split("|")]
        if len(cols) < 5:
            continue
        title_cell = cols[0]
        lm = re.match(r"\[(.+?)\]\((.+?)\)", title_cell)
        rep.papers.append({
            "title": lm.group(1) if lm else title_cell,
            "url": lm.group(2) if lm else "",
            "authors": cols[1],
            "year": cols[2],
            "citations": cols[3],
            "source": cols[4],
        })

    # Per-paper summaries
    m = re.search(r"## Per-Paper Summaries\s*\n+(.*?)(?=\n## )", text, re.S)
    if m:
        rep.paper_summaries = [
            ln.lstrip("- ").strip()
            for ln in m.group(1).splitlines()
            if ln.strip().startswith("-")
        ]

    # Gaps
    gap_section = text.split("## Research Gap Analysis", 1)
    if len(gap_section) == 2:
        body = gap_section[1]
        category = "Uncategorised"
        current = None
        for line in body.splitlines():
            h3 = re.match(r"^###\s+(.+)$", line)
            h4 = re.match(r"^####\s+(?:[^\w\s]*\s*)?(.+)$", line)
            if h3:
                category = h3.group(1).strip()
                continue
            if h4:
                current = Gap(title=h4.group(1).strip(), category=category)
                rep.gaps.append(current)
                continue
            if current is None:
                continue
            cm = re.search(r"\*\*Confidence:\*\*\s*(\w+)", line)
            if cm:
                current.confidence = cm.group(1).lower()
                continue
            rm = re.search(r"\*\*Reasoning:\*\*\s*(.+)", line)
            if rm:
                current.reasoning = rm.group(1).strip()
                continue
            if line.strip().startswith("- *"):
                current.evidence.append(line.strip("- ").strip())
    return rep


# ----------------------------------------------------------------------
# Paper generation
# ----------------------------------------------------------------------

SECTIONS = [
    ("Title, Abstract & Keywords", "Write the paper title (a single # heading), an ~200-word abstract, and 5-7 keywords."),
    ("Introduction", "Write the Introduction: motivate the problem, state the gap precisely, list 3-4 concrete contributions, and outline the paper."),
    ("Related Work", "Write the Related Work section, organised thematically. Cite ONLY the provided source papers using [n] numbering matching the reference list. Position the gap relative to each line of work."),
    ("Proposed Method", "Write the Methodology section: a precise problem formulation (with notation), the proposed approach addressing the gap, architecture/algorithm description, and design rationale. Use LaTeX-style math where helpful."),
    ("Experimental Design", "Write the Experimental Setup section: datasets/benchmarks that would be used, baselines, evaluation metrics, ablations, and implementation details. Be concrete and realistic; phrase as a proposed evaluation protocol."),
    ("Discussion, Limitations & Conclusion", "Write Expected Results & Discussion (hypothesised outcomes and why), Limitations, Ethics/Broader Impact, and Conclusion."),
    ("References", "Write the References section: a numbered list containing ONLY the provided source papers, formatted in IEEE style. Do not invent any references."),
]

SYSTEM_PROMPT = """You are an expert academic researcher writing a rigorous research paper for a top-tier venue.
Rules:
- Write in formal academic prose, markdown formatted.
- Cite ONLY the source papers provided, as [1]...[n] matching their order. NEVER fabricate references, results, or numbers from real experiments.
- Since no experiments have been run, frame empirical content as a proposed protocol and hypothesised/expected results.
- Be specific and technical, not vague. Avoid filler.
- Output only the requested section content, no meta-commentary."""


def build_context(rep: Report, gap: Gap) -> str:
    refs = "\n".join(
        f"[{i+1}] {p['title']} — {p['authors']} ({p['year']}). {p['url']}"
        for i, p in enumerate(rep.papers)
    )
    summaries = "\n".join(f"- {s}" for s in rep.paper_summaries)
    evidence = "\n".join(f"- {e}" for e in gap.evidence) or "(none listed)"
    return f"""TOPIC: {rep.topic}

EXECUTIVE SUMMARY OF GAP REPORT:
{rep.summary}

SOURCE PAPERS (the ONLY allowed references, cite as [n]):
{refs}

KEY FINDINGS FROM SOURCE PAPERS:
{summaries}

SELECTED RESEARCH GAP TO ADDRESS:
- Gap: {gap.title}
- Category: {gap.category}
- Confidence: {gap.confidence}
- Reasoning: {gap.reasoning}
- Evidence:
{evidence}
"""


def generate_paper(api_key: str, model: str, rep: Report, gap: Gap, progress_area):
    client = Groq(api_key=api_key)
    context = build_context(rep, gap)
    paper_parts = []
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context + "\nWe will write the paper section by section."},
        {"role": "assistant", "content": "Understood. I have the context and will write each section on request."},
    ]

    for i, (name, instruction) in enumerate(SECTIONS):
        status = progress_area.status(f"Writing: {name} ({i+1}/{len(SECTIONS)})")
        messages.append({"role": "user", "content": instruction})
        text = ""
        stream = client.chat.completions.create(
            model=model,
            max_tokens=6000,
            messages=messages,
            stream=True,
        )
        placeholder = status.empty()
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            text += delta
            placeholder.markdown(text[-1500:])
        messages.append({"role": "assistant", "content": text})
        paper_parts.append(text.strip())
        status.update(label=f"Done: {name}", state="complete")

    return "\n\n".join(paper_parts)


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------

st.set_page_config(page_title="Research Paper Writer", page_icon="📝", layout="wide")
st.title("📝 Research Paper Writer")
st.caption("Turn a research-gap report into a full research paper draft.")

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Groq API key", type="password",
                            help="Get one free at console.groq.com/keys")
    if Groq and api_key:
        model_options = list_groq_models(api_key)
    else:
        model_options = FALLBACK_MODELS
    model = st.selectbox("Model", model_options)
    st.divider()
    st.markdown("**How it works**\n1. Load a gap report (.md)\n2. Review the auto-ranked gaps\n3. Generate the paper\n4. Download the markdown")

uploaded = st.file_uploader("Upload a gap report (.md)", type=["md", "txt"])

# Also offer local reports next to the app
local_reports = sorted(Path(__file__).parent.glob("report_*.md"), reverse=True)
chosen_local = None
if local_reports and uploaded is None:
    chosen_local = st.selectbox(
        "...or pick a report from this folder",
        ["(none)"] + [p.name for p in local_reports],
    )

raw = None
if uploaded is not None:
    raw = uploaded.read().decode("utf-8", errors="replace")
elif chosen_local and chosen_local != "(none)":
    raw = (Path(__file__).parent / chosen_local).read_text(encoding="utf-8", errors="replace")

if raw:
    rep = parse_report(raw)
    if not rep.gaps:
        st.error("No research gaps found in this file. Is it a valid gap report?")
        st.stop()

    st.subheader(f"Topic: {rep.topic}")
    c1, c2 = st.columns(2)
    c1.metric("Papers analysed", len(rep.papers))
    c2.metric("Gaps found", len(rep.gaps))

    ranked = sorted(rep.gaps, key=lambda g: g.score, reverse=True)

    st.subheader("Research gaps (strongest first)")
    labels = [
        f"{'🥇 ' if i == 0 else ''}[{g.confidence}] {g.title}  (score {g.score:.1f})"
        for i, g in enumerate(ranked)
    ]
    idx = st.radio("Select the gap to write the paper on:", range(len(ranked)),
                   format_func=lambda i: labels[i])
    gap = ranked[idx]

    with st.expander("Gap details", expanded=True):
        st.markdown(f"**Category:** {gap.category}")
        st.markdown(f"**Confidence:** {gap.confidence}")
        st.markdown(f"**Reasoning:** {gap.reasoning}")
        if gap.evidence:
            st.markdown("**Evidence:**")
            for e in gap.evidence:
                st.markdown(f"- {e}")

    st.divider()
    if st.button("🚀 Generate research paper", type="primary", use_container_width=True):
        if Groq is None:
            st.error("The `groq` package is not installed. Run: pip install groq")
        elif not api_key:
            st.error("Enter your Groq API key in the sidebar.")
        else:
            progress_area = st.container()
            try:
                paper = generate_paper(api_key, model, rep, gap, progress_area)
            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()
            st.session_state["paper"] = paper
            st.session_state["paper_topic"] = rep.topic
            st.rerun()

if "paper" in st.session_state:
    st.divider()
    st.subheader("Generated paper")
    st.markdown(st.session_state["paper"])
    slug = re.sub(r"\W+", "_", st.session_state.get("paper_topic", "paper")).strip("_").lower()
    fname = f"paper_{slug}_{datetime.datetime.now():%Y%m%d_%H%M%S}.md"
    st.download_button("⬇️ Download paper (.md)", st.session_state["paper"],
                       file_name=fname, mime="text/markdown",
                       use_container_width=True)
