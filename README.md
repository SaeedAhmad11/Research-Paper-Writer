# 📝 Research Paper Writer

> **Turn a research-gap report into a full research paper draft — in minutes.**

Research Paper Writer is a Streamlit app that takes a structured Research Gap Report (markdown), automatically ranks the identified gaps by quality and confidence, and then uses a Groq-hosted LLM to write a complete, publication-ready paper draft section by section.

---

## ✨ Features

- **Auto-parses gap reports** — extracts topic, executive summary, source papers, and all identified research gaps from a structured markdown file.
- **Scores & ranks gaps** — each gap is scored based on its confidence level, category weight, and amount of supporting evidence, so the strongest opportunity surfaces first.
- **Section-by-section generation** — the paper is written incrementally (Title/Abstract → Introduction → Related Work → Methodology → Experiments → Discussion → References), with each section streamed live in the UI.
- **Multi-turn context** — each section is generated with full awareness of all prior sections, keeping the paper internally consistent.
- **Safe citation policy** — the model is instructed to cite *only* the source papers from your gap report. No hallucinated references.
- **Instant download** — the finished paper is exported as a clean `.md` file, ready to convert to PDF or LaTeX.
- **Dynamic model selection** — fetches the models available to your Groq API key at runtime, with a sensible fallback list.

---

## 🖥️ Demo

```
Upload gap_report.md  →  Pick a gap  →  Click Generate  →  Download paper.md
```

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.9+
- A free [Groq API key](https://console.groq.com/keys)

### 2. Install dependencies

```bash
pip install streamlit groq
```

### 3. Run the app

```bash
streamlit run app.py
```

### 4. Use the app

1. Paste your **Groq API key** into the sidebar.
2. Select a **model** (the app fetches your available models automatically).
3. **Upload** a gap report (`.md` or `.txt`) or place a `report_*.md` file in the same folder as `app.py` — it will appear in the dropdown.
4. Review the **ranked list of research gaps**.
5. Select the gap you want to address and click **🚀 Generate research paper**.
6. Watch each section generate live, then **download** the finished draft.

---

## 📄 Gap Report Format

The app expects a markdown report produced by a compatible research-gap-finder tool. The key sections it parses are:

```markdown
# Research Gap Report: <Topic>

## Executive Summary
...

## Source Papers
| # | Title | Authors | Year | Citations | Source |
...

## Per-Paper Summaries
- ...

## Research Gap Analysis

### <Category>

#### <Gap Title>
**Confidence:** high / medium / low
**Reasoning:** ...
- *Evidence from paper X*
```

Any gap report that follows this structure will work out of the box.

---

## ⚙️ Configuration

| Setting | Where | Description |
|---|---|---|
| Groq API Key | Sidebar | Required. Get one free at console.groq.com/keys |
| Model | Sidebar | Select from models available to your key |
| Gap selection | Main panel | Radio button ranked by composite score |

### Gap scoring formula

```
score = confidence_weight × category_weight + 0.2 × evidence_count
```

| Confidence | Weight |
|---|---|
| High | 3 |
| Medium | 2 |
| Low | 1 |

| Category | Weight |
|---|---|
| Method-Transfer Gaps | 1.0 |
| Orphaned Future Work | 0.8 |
| Other | 0.9 |

---

## 📁 Project Structure

```
.
├── app.py              # Main Streamlit application
├── report_*.md         # (Optional) Gap reports — auto-detected by the app
└── README.md
```

---

## 🛠️ Tech Stack

- [Streamlit](https://streamlit.io/) — UI framework
- [Groq Python SDK](https://github.com/groq/groq-python) — LLM inference
- Python standard library (`re`, `dataclasses`, `pathlib`, `datetime`)

---

## ⚠️ Limitations

- The generated paper is a **draft / proposed study** — no real experiments have been run. All empirical content is framed as a proposed protocol with hypothesised results.
- Paper quality depends on the quality of the input gap report and the source papers listed within it.
- Very large gap reports may hit Groq context limits depending on the selected model.

---

## 🤝 Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request for bug fixes, new features, or support for additional LLM providers.

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.
