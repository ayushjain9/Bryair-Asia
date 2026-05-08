# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The project uses a Windows venv at `.venv/`. Prefix commands accordingly:

```bash
# Rebuild the SQLite database from source Excel files in Data/
.venv/Scripts/python.exe prepare_data_final.py

# Run the Streamlit app (dev port 8765 is whitelisted in .claude/settings.local.json)
.venv/Scripts/python.exe -m streamlit run app.py --server.port 8765 --server.headless true --browser.gatherUsageStats false

# Health check
curl -s http://localhost:8765/_stcore/health

# CLI version of the AI agent (no Streamlit)
.venv/Scripts/python.exe agent_expert.py
```

Set `PYTHONIOENCODING=utf-8` if you see encoding errors from emoji/₹ output.

There is **no test suite** and **no linter** configured — verify changes by running the app and exercising affected pages.

## Required environment

`.env` (loaded via `python-dotenv` with `override=True`) must contain:
- `ANTHROPIC_API_KEY` — without it the AI Assistant page renders a blocking error and the CLI exits early.

The Streamlit Cloud deployment expects the same key under **Settings → Secrets**.

## Architecture

**Two-stage pipeline**, with a strict separation between data preparation (Excel → SQLite) and the consumer app (SQLite → UI/agent). The committed `procurement_final.db` is the contract between them.

### Stage 1 — Data prep (`prepare_data_final.py`)

Orchestrates all loaders. Reads 5 Excel files from `Data/` (gitignored, kept local — this is confidential procurement data) and rebuilds `procurement_final.db` from scratch every run. Composes two helpers:

- `forecasting.add_forecast_columns(df)` — recency-weighted moving average over 3 FYs (weights 0.5/0.3/0.2, renormalised when years missing) plus service-level safety stock `SS* = z(sl) * σ_annual * sqrt(LT_days/365)` at 95/98/99%. Documented limitation: σ from 3 yearly observations is noisy — Z-class items flagged as least reliable.
- `supplier_analytics.compute_supplier_risk(conn)` — weighted risk score (40% single-source A-class / 30% spend share / 20% lead-time σ / 10% coverage), each factor normalised to its population max so the score is **relative to the current supplier portfolio** and re-baselined on every rebuild.

Resulting tables (always in this DB):
- `stock_master` (~7.8k rows, all 4 plants) — adds ABC/XYZ classification, forecasts, optimal SS
- `planning_master` (~1.1k rows, P9 + 21C only) — adds enhanced TBO via ROP method, `is_critical` flag (below safety AND no order placed)
- `supplier_master`, `supplier_risk`, `tbo_orders`, `pending_orders`, `stock_by_location`
- Views: `v_warehouse_summary`, `v_critical_materials`

The `is_critical` flag and the TBO formula are the dashboard's two most important derived columns — both computed here, not in the app.

### Stage 2a — Streamlit dashboard (`app.py`)

Single-file 5-page app: Overview, Optimization, Inventory, Forecast & SS, AI Assistant. Helpers:
- `q(sql)` — one-shot read-only SQL → DataFrame
- `fmt(v)` — Indian currency (₹L = lakh, ₹Cr = crore); use this everywhere money is shown
- `stat_card`, `section_header`, `alert_box`, `dark_*` chart wrappers — all consume the `C` design-token dict and a shared `plotly_base()` layout

The UI is a "Mission Control" dark theme. Streamlit's default chrome is overridden with a large CSS block at the top — when modifying expanders or buttons, search for the matching `[data-testid="..."]` selector rather than fighting Streamlit defaults. The expander selector in particular has been hardened against `arrow_right` Material-icon text leaking through on Streamlit Cloud (commits eb8a749, d17280d, 65e46c1).

### Stage 2b — Tool-calling agent (`agent_expert.py`)

Native Anthropic `client.messages.create(...)` loop (model: `claude-sonnet-4-20250514`, hardcoded) — **not** LangChain. Exposes 4 tools to the model:

| Tool | Purpose |
|------|---------|
| `query_db(sql)` | Read-only SELECT against the DB |
| `forecast_material(material_code)` | Per-material forecast + SS at 95/98/99% |
| `supplier_risk(supplier_name)` | Per-supplier risk scorecard |
| `draft_pr(material_code, qty, ...)` | Build a PR row (NOT submitted — UI accumulates and offers Excel download) |

The `chat()` entrypoint loops up to `MAX_TOOL_ITERATIONS = 8` times, dispatching tool calls and feeding results back. It returns `{reply, tool_calls, history}`; the Streamlit page round-trips `history` through `st.session_state['ai_chat_history']` to give the agent memory across turns (capped at `HISTORY_TURN_CAP * 3 = 60` messages).

**SQL guardrails** in `_validate_select()`: rejects anything that isn't a single SELECT (sqlglot parse + a forbidden-keywords regex), auto-appends `LIMIT 500`, and the connection runs with `PRAGMA query_only = 1` as a second line of defence. Tool result payloads are also truncated at `TOOL_RESULT_CHAR_CAP = 8000` chars to bound the context.

The system prompt is built per-turn from a live `get_schema()` introspection so it stays in sync with whatever the latest `prepare_data_final.py` produced.

## Domain context

- **Multi-warehouse**: P9 and 21C are active planning warehouses; 419 AT and 419 PD are historical stock-only and appear in `stock_master` / `stock_by_location` but not `planning_master`.
- **TBO** ("To Be Ordered") = the system's recommendation for what to order next. Formula in `prepare_data_final.calculate_enhanced_tbo`: `TBO = max(0, ROP − (Stock + Pending − Allocations))`, rounded up to nearest 10.
- **`is_critical`** = below safety stock AND no purchase order placed. This is the most surfaced metric.
- The `KNOWLEDGE_BASE` constant in `agent_expert.py` (TBO logic, SS reduction matrix, ABC-XYZ strategy, KPI targets) is part of the agent's system prompt — update it there when domain heuristics change.

## Files NOT in the deployed app

`.gitignore` excludes `generate_docs.py` and `generate_technical_doc.py` — these are local utilities that emit client-facing Word / PowerPoint documents into `Doc/`. They are not imported by `app.py` and don't need to run for the app to work.

`Data/` (source Excel files) is also gitignored. The committed `procurement_final.db` is what the deployed Streamlit Cloud app reads; you only need `Data/` if you want to rebuild the DB locally.
