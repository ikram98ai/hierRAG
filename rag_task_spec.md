# RAG Evaluation Task: Hierarchical Metadata RAG vs Standard RAG (Accuracy & Speed)

## 1. Objective
Build a Retrieval-Augmented Generation (RAG) system from uploaded PDF/TXT documents and compare two pipelines within the same UI:
- **Hierarchical RAG (Hier-RAG):** applies hierarchical classification and metadata tagging, then retrieves within filtered subsets.
- **Standard RAG (Base-RAG):** baseline retrieval without hierarchical pre‑filtering.

Expose **only main functions** (no helpers) via Gradio’s auto‑generated API and also as an MCP server. Deploy on **Hugging Face Spaces**.

---

## 2. Timeline
- Estimated duration: **3–4 days**

---

## 3. Deliverables
1. **Gradio App** deployed to a **Private Space** under the AP‑UW Organization (access will be granted upon sharing your HF account).
   - Code includes **type hints** and **docstrings**.
   - Public API = **only** the app’s main functions (helpers remain private).
   - **MCP server** available alongside the app (document how to connect).
2. **README.md** with setup, environment variables, usage, deployment, and evaluation steps.
3. **Quantitative Evaluation Report** (in repo) comparing **Base‑RAG vs Hier‑RAG** on a public or custom dataset; include methodology, metrics, and CSV/JSON outputs.

---

## 4. Required Skills
- Python; RAG (LLMs/embeddings/vector DBs)
- Gradio and Hugging Face Spaces
- `gradio_client` usage and MCP server integration

---

## 5. Repository Layout (Simplified)
```
.
├─ app.py                # Spaces entry; defines UI and exposed functions (with api_name)
├─ core/                 # Internal logic (NOT publicly exposed)
│  ├─ ingest.py          # Loaders, hierarchical classification, chunking
│  ├─ index.py           # Embeddings, vector DB, metadata filters
│  ├─ retrieval.py       # Base‑RAG / Hier‑RAG pipelines
│  ├─ eval.py            # Metrics: Hit@k, MRR, latency, similarity
│  └─ utils.py           # Shared helpers (e.g., PII masking)
├─ tests/                # ≥10 pytest cases
├─ requirements.txt      # gradio, gradio_client, faiss/chromadb, etc.
└─ README.md
```
**Notes:** Entry file must be `app.py` at the repo root. Only functions bound to UI events with `api_name` are exposed as API.

---

## 6. Data Requirements
- Support multiple PDF/TXT uploads.
- **Hierarchy definitions** must live in **external YAML or JSON** files.
- Provide **three preset hierarchies**:
  1. **Hospital** (medical documentation structure)
  2. **Bank** (financial/banking business structure)
  3. **Fluid Simulation** (scientific/technical reporting structure)
  *Use public or self‑authored definitions; they must be reasonable and relevant.*
- Target **3 levels** (e.g., `domain > section > topic`).
- **Metadata schema (example)** applied at **chunk level** (prefer page/heading boundaries):
  ```json
  {
    "doc_id": "uuid",
    "chunk_id": "uuid",
    "source_name": "filename.pdf",
    "lang": "ja|en",
    "level1": "domain",
    "level2": "section",
    "level3": "topic",
    "doc_type": "policy|manual|faq"
  }
  ```

---

## 7. Models & Vector Database
- **Embeddings:** flexible (e.g., OpenAI, bge‑m3).
- **Vector DB (choose one):**
  - **Self‑hosted in Space:** e.g., **Chroma** persisted under `/data/chroma` (use Persistent Storage).
  - **Managed external service:** e.g., Qdrant Cloud / Pinecone / Weaviate Cloud (secrets managed via HF Space Secrets).
- Must support **metadata filtering** for hierarchical tags (level1/2/3, `doc_type`, etc.).

---

## 8. Retrieval Pipelines
**Base‑RAG**
1. Vector similarity search
2. Optional re‑ranking
3. Prompt → Answer

**Hier‑RAG**
1. Pre‑filter by hierarchical tags
2. Vector search within the filtered subset
3. Optional re‑ranking (bonus for hierarchy match)
4. Prompt → Answer

The UI should present **side‑by‑side results** (answers, supporting snippets, latency).

---

## 9. UI Requirements
- **(1) Upload:** Multiple PDF/TXT uploads with **extension validation** and preview.
- **(2) Build RAG:** Build index from uploaded data (show progress, counts, and size).
- **(3) Search:** Query against the built RAGs for **post‑delivery qualitative evaluation**.
- **(4) Chat:** Conversational **chat UI** for qualitative testing; show retrieved sources/contexts.
- **Evaluate:** Provide quantitative/qualitative metrics (Hit@k, MRR, latency) and export CSV/JSON.
- **API Export:** Bind functions with `api_name` (e.g., `btn.click(..., api_name="compare")`) so they’re auto‑exposed (usable via `gradio_client`).

---

## 10. Evaluation
- **Quantitative:** Compare **Base‑RAG vs Hier‑RAG** on a public or custom dataset; report Hit@k, MRR, semantic similarity, and latency. Save CSV/JSON to `reports/` and summarize in markdown.
- **Qualitative:** Use Search and Chat UIs to manually inspect answer relevance and evidence clarity.
- Evaluation routines should also be callable via the Gradio API (automation friendly).

---

## 11. Tests
- Provide ≥10 `pytest` cases covering: chunking, hierarchy/tag assignment, metadata filters, retrieval, evaluation metrics, and API behaviors.

