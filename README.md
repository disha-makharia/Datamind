# DataMind: Agents 1 to 4 (Supervisor, Data, SQL, RAG)

This is the first working half of the DataMind architecture from your deck: user question → FastAPI → LangGraph → the first four specialist agents → a temporary response node. The Analysis, Visualization and Response agents (5 to 7) plug into the same graph later.

The LLM is **GPT-OSS 120B on the free Groq API**. The client is OpenAI-compatible, so switching to xAI Grok, or to Ollama as drawn in your architecture slide, is a `.env` change only.

---

## 1. What's in the box

```
datamind/
├── config.py              settings (reads .env)
├── llm.py                 Groq/xAI client: chat() and chat_json()
├── state.py               shared LangGraph state
├── data_hub.py            DuckDB: load CSV/JSON/Parquet/Excel, schema catalog, SQL guard
├── agents/
│   ├── supervisor.py      Agent 1: understand, plan, route
│   ├── data_agent.py      Agent 2: pick tables/columns (schema linking)
│   ├── sql_agent.py       Agent 3: write, validate, run, self-correct SQL
│   ├── rag_agent.py       Agent 4: search docs, extract reasons with citations
│   └── interim_response.py  TEMPORARY stand-in for agents 5-7
├── rag/
│   ├── ingest.py          PDF → text → chunks → local embeddings → ChromaDB
│   └── store.py           ChromaDB collection + semantic search
├── graph.py               LangGraph orchestrator (routing)
├── main.py                FastAPI backend (also serves the UI)
├── static/                web UI (served by FastAPI at /)
│   ├── index.html         app shell
│   ├── css/app.css        styles, light + dark themes
│   └── js/                api.js, store.js, components.js, chart.js, app.js
├── cli.py                 terminal client (easiest for demos)
├── data/                  dummy dataset (CSV + JSON) loaded at startup
├── docs/                  dummy company PDFs for RAG
├── sample_files/          same dataset as one Excel workbook (for upload demo)
├── scripts/               generators for the dummy data and PDFs
├── tests/test_offline.py  full-graph test with a fake LLM (no API key needed)
└── eval/                  12 gold questions + execution-accuracy evaluation
```

---

## 2. Setup (about 10 minutes)

**Step 1. Python 3.10 or newer** (3.11 recommended). Create a virtual environment:

```bash
cd datamind
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

`sentence-transformers` pulls in PyTorch, so this download is large. That's expected.

**Step 2. Get a free Groq API key.** Sign in at console.groq.com, open API Keys, and create a key. The full key is shown only once, so copy it with the copy button straight away. No credit card is needed.

**Step 3. Configure.**

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Put your key in `GROQ_API_KEY`, with no spaces or quotes. Leave `LLM_MODEL=openai/gpt-oss-120b` (keep the `openai/` prefix). Groq retires models from time to time; if you ever get a 404 `model_not_found`, pick a current model from Groq's Models page, for example `qwen/qwen3.6-27b`. Never commit `.env` or paste your key anywhere public.

**Step 4. Check wiring without spending credits.**

```bash
python tests/test_offline.py
```

This runs the entire graph with a fake LLM. You should see the Supervisor route to both data and RAG, the Data Agent reject a hallucinated table, and the SQL Agent fail once and self-correct.

**Step 5. Index the company documents.**

```bash
python -m rag.ingest
```

The first run downloads the `all-MiniLM-L6-v2` embedding model (about 90 MB) from Hugging Face. After that, embeddings run locally and free. Re-run this whenever you add or edit files in `docs/`.

**Step 6. Ask questions.**

```bash
python cli.py "Which product had the highest sales in 2025?"
python cli.py        # interactive mode
```

**Step 7. Run the API.**

```bash
uvicorn main:app --reload
```

Open **http://127.0.0.1:8000** for the DataMind web app:

- **Ask**: chat with your data. Each agent lights up live as it finishes (streamed from `/ask/stream`). Answers have tabs for the chart, result table (sortable, filterable, CSV download), highlighted SQL with every self-correction attempt, document sources with retrieved passages, and the full agent trace with the Supervisor's plan. Chats are saved in the browser, and can be searched, renamed, exported to Markdown and deleted.
- **Data**: browse every table, its columns and their values, preview rows, upload new datasets by drag and drop, and remove uploaded ones.
- **Documents**: semantic search across company documents (the same search the RAG agent uses), upload and remove documents.
- Light and dark themes, settings, and keyboard shortcuts (press `?` in the app).

http://127.0.0.1:8000/docs is the Swagger UI for testing the raw API.

| Endpoint | Purpose |
|---|---|
| `GET /health` | provider, model, loaded tables |
| `GET /tables` | full schema catalog |
| `POST /ask` | `{"question": "...", "debug": true}` runs the agents |
| `POST /ask/stream` | same, as Server-Sent Events: one event per agent, then the answer |
| `GET /tables/{name}/preview` | first rows of a table |
| `DELETE /tables/{name}` | remove an uploaded table |
| `GET /documents` | indexed documents with passage counts |
| `GET /documents/search?q=` | semantic search over documents |
| `DELETE /documents/{name}` | remove a document from the index |
| `POST /upload/dataset` | upload CSV / JSON / Parquet / XLSX → new DuckDB table(s) |
| `POST /upload/document` | upload PDF / TXT / MD → indexed into ChromaDB |

---

## 3. How each agent works

### Agent 1: Supervisor (`agents/supervisor.py`)
Receives the question plus a list of table names and indexed documents. The LLM returns a JSON plan: `intent` (`data_only`, `docs_only`, `data_and_docs`, `out_of_scope`), a rewritten `data_task` for the SQL side, a `doc_query` for the search side, and a `needs_chart` flag reserved for the Visualization Agent later. The plan is sanity-checked (for example, RAG is skipped if no documents are indexed), and if the LLM call fails a keyword heuristic takes over so the pipeline never dead-ends.

### Agent 2: Data Agent (`agents/data_agent.py`)
Solves *schema linking*, the problem DIN-SQL and MAC-SQL in your literature review identify as a major source of Text-to-SQL errors. It sends the LLM a rich catalog built by `data_hub.py`: every column with its type, and either all distinct values (for low-cardinality columns such as `region`), examples, or min/max ranges. Seeing that `region` holds `'West'` rather than `'west'`, or that dates span 2024 to 2025, prevents a large class of wrong queries. The LLM's selection is then validated against the real catalog, and hallucinated tables or columns are dropped.

### Agent 3: SQL Agent (`agents/sql_agent.py`)
Writes one DuckDB query from the focused schema plus the Data Agent's join and filter hints. Every query passes through `DataHub.validate_sql()` before execution, which uses `sqlglot` to allow only a single `SELECT`, only known tables, and no file-reading functions such as `read_csv('/etc/passwd')`. If validation or execution fails, the error message goes back to the LLM and it rewrites the query, up to `SQL_MAX_RETRIES` times. A query that returns zero rows gets one extra review, because an empty result usually means a wrong filter value. This is the "refiner" / self-correction idea from MAC-SQL and DIN-SQL, and every attempt is stored in `sql_attempts` for your evaluation.

### Agent 4: RAG Agent (`agents/rag_agent.py`)
Searches ChromaDB with the Supervisor's `doc_query`, discards low-similarity chunks, and asks the LLM to extract only what the excerpts actually say, with `[file, page]` citations. It runs *after* the SQL Agent on purpose: it receives the SQL findings, so if SQL shows West Electronics fell in Q3, the RAG summary focuses on the explanation for that drop.

### Orchestration (`graph.py`)

| Question type | Route |
|---|---|
| data only | supervisor → data → sql → response |
| data + docs | supervisor → data → sql → rag → response |
| docs only | supervisor → rag → response |
| out of scope | supervisor → response |

`state.py` defines the shared state; each agent returns only the keys it changes, and `trace` accumulates a readable log of what every agent did.

---

## 4. The dummy dataset (NovaMart, a fictional Indian retailer)

| Table | Rows | Contents |
|---|---|---|
| `sales` | ~11,000 | orders, Jan 2024 to Dec 2025, INR amounts, channel, discount, payment method |
| `products` | 32 | 5 categories: Electronics, Home & Kitchen, Fashion, Grocery, Beauty |
| `customers` | 1,500 | city, region (West/North/South/East), segment |
| `stores` | 14 | 13 physical stores + `S00` online (region `National`) |
| `returns` | ~430 | reason, refund, status; join on `order_id` |
| `marketing_campaigns` | 9 | JSON file; dates, budgets, target category |

Revenue is `total_amount = quantity × unit_price × (1 − discount_pct/100)`. Regenerate any time with `python scripts/generate_data.py` (seeded, so results are reproducible).

The data has **five deliberate stories**, and the PDFs in `docs/` explain them. This is what lets you demo SQL and RAG working together:

1. West-region Electronics revenue collapses July to September 2025 → Bhiwandi warehouse flood (Q3 Business Review).
2. Electronics and Fashion spike 15 Oct to 15 Nov 2025 → Festive Dhamaka campaign (Campaign Report).
3. NovaSound X2 Earbuds returns spike April to June 2025 → battery batch B-0325 (Quality & Returns Memo).
4. South overtakes West by order count in 2025 → two new stores opened Feb 2025 (Expansion Update).
5. Home & Kitchen bumps every April to May → Summer Cool Deals (Pricing & Discount Policy).

### Demo questions

- Data only: *"Which product had the highest sales in 2025?"*, *"Top 3 stores by revenue in 2025"*, *"Monthly revenue trend for Fashion in 2025"*
- Data + docs: *"Why did Electronics sales in the West region drop in Q3 2025?"*, *"Why did NovaSound X2 Earbuds have so many returns?"*, *"Why did South region orders grow in 2025?"*
- Docs only: *"What is our return policy for electronics?"*, *"What is the maximum discount a store manager can give?"*

---

## 5. Evaluation (for your Research Parameters slide)

```bash
python eval/run_eval.py
```

This runs 12 questions with hand-written gold SQL and reports **execution accuracy** (does the agent's result match the gold result, ignoring column names, order and extra columns), **average response time**, and **average SQL attempts** (how often self-correction kicked in). Results are saved to `eval/results.csv` for your report. Add more questions to `eval/questions.json` as you go; aim for a mix of easy, join-heavy and date-heavy ones.

A good experiment for your report: run the eval with `SQL_MAX_RETRIES=1` (no self-correction) and again with `3`, and compare accuracy.

---

## 6. About AWS Athena

Your agent cards slide says the SQL Agent "runs query on AWS Athena", while the architecture slide is the free/local DuckDB version. This code implements DuckDB, which is what the architecture and tech-stack slides show. If you later want Athena, only `DataHub.run_query()` changes, plus the dialect line in the SQL Agent prompt (Athena uses Trino SQL):

```python
# pip install pyathena
from pyathena import connect
conn = connect(s3_staging_dir="s3://your-bucket/athena-results/", region_name="ap-south-1")
cur = conn.cursor()
cur.execute(sql)
columns = [d[0] for d in cur.description]
rows = cur.fetchmany(limit)
```

The Data Agent's catalog would then come from the Glue Data Catalog instead of DuckDB's `information_schema`. It's worth aligning the slides so the examiners see one consistent story.

---

## 7. Next: agents 5 to 7

Replace `interim_response` in `graph.py` with three nodes:

- **Analysis Agent**: reads `sql_result` + `rag_summary`, computes growth rates and highlights trends (use pandas on the result rows, and let the LLM interpret).
- **Visualization Agent**: runs when `plan["needs_chart"]` is true; generates a Plotly figure from `sql_result` and returns it as JSON for the frontend.
- **Response Agent**: validates (does the answer's numbers match `sql_result`? are citations real sources?) and writes the final answer.

Add their keys to `state.py`, add nodes and edges in `build_graph()`. Nothing in agents 1 to 4 needs to change.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `Set XAI_API_KEY in your .env file` | `.env` missing or key blank; it must sit next to `config.py` |
| `model not found` / 404 | the model was retired or mistyped; pick a current id from Groq's Models page |
| 401 / 403 | wrong or incomplete key; create a new one and copy it with the copy button |
| 429 rate limit | free-tier limit reached; wait a minute and ask again |
| RAG returns nothing | run `python -m rag.ingest` first |
| first ingest hangs | it's downloading the embedding model once; needs internet |
| SQL keeps failing | call `/ask` with `"debug": true` and read `sql_attempts` to see each error |
| Excel upload creates odd table names | sheet names become table names (lowercased, spaces → `_`) |
