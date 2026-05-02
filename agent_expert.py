"""
Procurement Analytics Agent (v4.0 — Tool-Calling)
==================================================
A single Anthropic tool-calling agent that replaces the previous classifier +
dual-handler design. Used by both:
  • the Streamlit AI Assistant page (via chat())
  • the CLI (via main())

Tools exposed
-------------
  query_db(sql)               read-only SELECT against procurement_final.db
  forecast_material(code)     pulls forecast + optimal SS for a material
  supplier_risk(name)         pulls supplier-level risk score & metrics
  draft_pr(code, qty, ...)    builds a structured purchase-requisition row
                              (NOT submitted — the UI accumulates drafts and
                              exposes a download button)

SQL guardrails
--------------
The query_db tool parses the statement with sqlglot and rejects anything that
isn't a single SELECT. Auto-appends LIMIT 500 to bound result size. The
connection is opened with PRAGMA query_only = 1 as a second line of defence.

Memory
------
The chat() entrypoint takes a `history` list and returns the full updated
message list. Streamlit stores this in session_state across turns.
"""

import os
import json
import sqlite3
import re
from datetime import datetime

import pandas as pd
import sqlglot
from anthropic import Anthropic
from dotenv import load_dotenv

# override=True so .env wins over an inherited empty ANTHROPIC_API_KEY
# (e.g. when launched from a sandbox that blanks the env var).
load_dotenv(override=True)

DB_PATH = 'procurement_final.db'
MODEL = 'claude-sonnet-4-20250514'
MAX_TOOL_ITERATIONS = 8
TOOL_RESULT_CHAR_CAP = 8000

KNOWLEDGE_BASE = """
# Inventory & Procurement Expert Knowledge

## TBO (To Be Ordered) Logic
TBO = Reorder Point − (Current Stock + Pending − Allocations)
ROP = (Lead Time × Daily Demand) + Safety Stock

## Safety Stock Reduction Matrix
| Profile               | Action            | New Level           |
|-----------------------|-------------------|---------------------|
| Low Vol + Non-Critical| REDUCE 40-50%     | 7-10 days coverage  |
| Low Vol + Critical    | REDUCE 20-30%     | 15-20 days coverage |
| High Vol + Non-Crit   | REDUCE 10-20%     | 20-25 days coverage |
| High Vol + Critical   | MAINTAIN/INCREASE | 30-45 days coverage |

## ABC-XYZ Strategy
- AX: JIT, tight control, 2-3 weeks safety stock
- AZ: Higher buffer, dual sourcing
- CX: Bulk orders, 8-12 weeks safety stock
- CZ: Accept higher stock, minimise admin

## KPI Targets
| Metric                  | Target      |
|-------------------------|-------------|
| Inventory Turnover      | 8-12x       |
| Days of Inventory       | 30-45 days  |
| Stockout Rate           | <3%         |
| Dead Stock %            | <2%         |
| Safety Stock Compliance | >95%        |
"""


# ── Schema introspection (used for system prompt) ────────────────────────────
def get_schema():
    conn = sqlite3.connect(DB_PATH)
    schema_parts = []
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        schema_parts.append(f"  {table} ({n} rows): {', '.join(cols)}")
    conn.close()
    return "\n".join(schema_parts)


# ── SQL guardrail ─────────────────────────────────────────────────────────────
_FORBIDDEN_KEYWORDS = re.compile(
    r'\b(insert|update|delete|drop|alter|create|attach|detach|pragma|replace|truncate|vacuum)\b',
    re.IGNORECASE,
)


def _validate_select(sql: str) -> str:
    """
    Reject anything but a single SELECT. Append LIMIT 500 if missing.
    Raises ValueError on any violation.
    """
    sql = sql.strip().rstrip(';').strip()
    if not sql:
        raise ValueError('Empty SQL statement.')

    if _FORBIDDEN_KEYWORDS.search(sql):
        raise ValueError('Only SELECT statements are allowed.')

    try:
        parsed = sqlglot.parse(sql, dialect='sqlite')
    except Exception as e:
        raise ValueError(f'SQL parse error: {e}')

    if len(parsed) != 1 or parsed[0] is None:
        raise ValueError('Exactly one SELECT statement is required.')

    if parsed[0].key.lower() != 'select':
        raise ValueError(f"Only SELECT allowed; got '{parsed[0].key.upper()}'.")

    if not re.search(r'\blimit\b', sql, re.IGNORECASE):
        sql = f'{sql} LIMIT 500'
    return sql


# ── Tool implementations ──────────────────────────────────────────────────────
def tool_query_db(sql: str) -> dict:
    try:
        sql = _validate_select(sql)
    except ValueError as e:
        return {'error': str(e), 'sql': sql}

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute('PRAGMA query_only = 1')
        df = pd.read_sql_query(sql, conn)
    except Exception as e:
        return {'error': str(e), 'sql': sql}
    finally:
        conn.close()

    sample = df.head(50).to_dict(orient='records')
    return {
        'sql': sql,
        'row_count': len(df),
        'columns': df.columns.tolist(),
        'rows': sample,
        'truncated': len(df) > 50,
    }


def tool_forecast_material(material_code: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM stock_master WHERE material_code = ? LIMIT 1",
            conn, params=[material_code],
        )
    finally:
        conn.close()

    if df.empty:
        return {'error': f'Material {material_code!r} not found in stock_master.'}

    r = df.iloc[0]

    def _f(v):
        try:
            return None if pd.isna(v) else float(v)
        except (TypeError, ValueError):
            return v

    return {
        'material_code': r['material_code'],
        'description': r.get('description'),
        'consumption_history': {
            'fy_2022_23': _f(r.get('fy_2022_23')),
            'fy_2023_24': _f(r.get('fy_2023_24')),
            'fy_2024_25': _f(r.get('fy_2024_25')),
        },
        'forecast_next_year': _f(r.get('forecast_next_year')),
        'forecast_band_lower': _f(r.get('forecast_lower_band')),
        'forecast_band_upper': _f(r.get('forecast_upper_band')),
        'safety_stock_current': _f(r.get('safety_stock_hist')),
        'safety_stock_optimal': {
            '95': _f(r.get('safety_stock_optimal_95')),
            '98': _f(r.get('safety_stock_optimal_98')),
            '99': _f(r.get('safety_stock_optimal_99')),
        },
        'lead_time_days': _f(r.get('lead_time_days')),
        'consumption_volatility': _f(r.get('consumption_volatility')),
        'abc_class': r.get('abc_class'),
        'xyz_class': r.get('xyz_class'),
    }


def tool_supplier_risk(supplier_name: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if 'supplier_risk' in tables:
            df = pd.read_sql_query(
                "SELECT * FROM supplier_risk WHERE supplier_name = ? LIMIT 1",
                conn, params=[supplier_name],
            )
        else:
            df = pd.read_sql_query(
                "SELECT * FROM supplier_master WHERE supplier_name = ? LIMIT 1",
                conn, params=[supplier_name],
            )
    finally:
        conn.close()

    if df.empty:
        return {'error': f'Supplier {supplier_name!r} not found.'}

    return {k: (None if pd.isna(v) else v) for k, v in df.iloc[0].to_dict().items()}


def tool_draft_pr(material_code: str, qty: float,
                  supplier: str = None, justification: str = '') -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            """SELECT material_code, description, warehouse, supplier_name,
                      unit_price, lead_time_weeks
               FROM planning_master WHERE material_code = ? LIMIT 1""",
            conn, params=[material_code],
        )
    finally:
        conn.close()

    if df.empty:
        return {'error': f'Material {material_code!r} not in planning_master.'}

    r = df.iloc[0]
    chosen = supplier or r.get('supplier_name') or 'TBD'
    unit_price = float(r.get('unit_price') or 0)
    return {
        'status': 'DRAFT',
        'material_code': material_code,
        'description': r.get('description'),
        'warehouse': r.get('warehouse'),
        'supplier': chosen,
        'qty': float(qty),
        'unit_price': unit_price,
        'order_value': round(unit_price * float(qty), 2),
        'lead_time_weeks': float(r.get('lead_time_weeks') or 0) or None,
        'justification': justification,
        'drafted_at': datetime.now().isoformat(timespec='seconds'),
    }


# ── Tool registry (Anthropic native schemas) ──────────────────────────────────
TOOLS = [
    {
        'name': 'query_db',
        'description': (
            "Run a read-only SQLite SELECT against the procurement database. "
            "Tables: stock_master (7,819 rows; ABC/XYZ, forecast_next_year, "
            "safety_stock_optimal_95/98/99, ss_delta_value_95/98/99), "
            "planning_master (1,123 P9+21C items; current_stock, safety_stock, "
            "tbo_qty, supplier_name, is_critical), supplier_master (aggregates), "
            "supplier_risk (risk_score, risk_tier, single_source_a_count, spend_pct), "
            "tbo_orders, pending_orders, stock_by_location. "
            "Only SELECT allowed. Auto-limited to 500 rows."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'sql': {'type': 'string', 'description': 'A single SQLite SELECT statement.'},
            },
            'required': ['sql'],
        },
    },
    {
        'name': 'forecast_material',
        'description': (
            "Look up demand forecast and optimal safety-stock recommendations "
            "for a single material. Returns 3-year FY history, next-year forecast "
            "with ±2σ band, current SS, optimal SS at 95/98/99% service levels, "
            "lead time, ABC/XYZ class. Use this for any 'how much should we keep "
            "of X' or 'what's next year's demand for X' question."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'material_code': {'type': 'string', 'description': 'Exact material code (e.g. "48060").'},
            },
            'required': ['material_code'],
        },
    },
    {
        'name': 'supplier_risk',
        'description': (
            "Look up risk metrics for a supplier: composite risk_score (0-100), "
            "risk_tier (Low/Medium/High/Critical), spend_pct, "
            "single_source_a_count (sole-supplied A-class items), lt_std_weeks, "
            "warehouse_count. Use this when the user asks about supplier risk, "
            "concentration, or single-source exposure."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'supplier_name': {'type': 'string', 'description': 'Exact supplier name as in planning_master.'},
            },
            'required': ['supplier_name'],
        },
    },
    {
        'name': 'draft_pr',
        'description': (
            "Generate a draft purchase requisition for a material. The PR is NOT "
            "submitted — it is queued in the UI for the user to review and download "
            "as Excel. Use this when the user asks you to 'order', 'place a PO for', "
            "or 'create a requisition for' a material. Always include a 'justification' "
            "string grounded in data (e.g. 'Below safety stock by 50 units; lead time "
            "12 weeks; supplier EEC')."
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'material_code': {'type': 'string'},
                'qty': {'type': 'number', 'description': 'Order quantity in material UOM.'},
                'supplier': {'type': 'string', 'description': 'Supplier override; omit to use planning_master default.'},
                'justification': {'type': 'string', 'description': 'Short rationale grounded in data.'},
            },
            'required': ['material_code', 'qty'],
        },
    },
]


_TOOL_DISPATCH = {
    'query_db':          lambda i: tool_query_db(i['sql']),
    'forecast_material': lambda i: tool_forecast_material(i['material_code']),
    'supplier_risk':     lambda i: tool_supplier_risk(i['supplier_name']),
    'draft_pr':          lambda i: tool_draft_pr(
        i['material_code'], i['qty'],
        i.get('supplier'), i.get('justification', ''),
    ),
}


# ── System prompt ─────────────────────────────────────────────────────────────
def _build_system_prompt():
    return f"""You are a Senior Procurement Consultant (20+ years manufacturing experience), serving the procurement team at Bryair Asia.

OPERATING ENVIRONMENT
This is a multi-warehouse procurement system with two active warehouses (P9 and 21C) plus historical stock at 419 AT and 419 PD.

DATABASE SCHEMA (current snapshot)
{get_schema()}

DOMAIN KNOWLEDGE
{KNOWLEDGE_BASE}

TOOLS YOU CAN USE
- query_db: read-only SQL for ad-hoc data lookups
- forecast_material: per-material forecast + optimal SS at 95/98/99% service levels
- supplier_risk: per-supplier risk score and concentration metrics
- draft_pr: generate a draft purchase requisition (queued for user review, not submitted)

RESPONSE STYLE
- For factual lookups ("show me…", "list…", "how many…"): keep it tight. One short paragraph + a small table or bullet list.
- For strategic questions ("should we…", "how do we reduce…", "compare…"): structure as
    1. Direct Answer  (1-2 sentences with a clear recommendation)
    2. Data Analysis  (cite specific numbers from your tool calls)
    3. Recommendations  (Immediate / Short-term)
    4. Risks
    5. ₹ Impact
    6. Action Checklist
- Always cite specific numbers from your tool calls — never invent data.
- When discussing safety stock, prefer the optimal SS values from forecast_material over arbitrary heuristics.
- When the user asks to "order" or "place a PO", call draft_pr — don't just describe what they should do.
- Compare warehouses (P9 vs 21C) when relevant.
- Use ₹ formatting (₹1L = ₹100,000, ₹1Cr = ₹10,000,000). Round large numbers.

CONSTRAINTS
- query_db is auto-limited to 500 rows. If you need a count, write COUNT(*) — don't paginate.
- Trust the schema above; don't query sqlite_master.
- Never claim to have submitted, sent, or executed an order. draft_pr only queues drafts for user download.
"""


# ── Main entrypoint ───────────────────────────────────────────────────────────
def chat(user_message: str, history: list = None, client: Anthropic = None) -> dict:
    """
    Run one conversation turn. Loops through tool calls until the model returns
    a final text response (or hits MAX_TOOL_ITERATIONS).

    Args:
        user_message: latest user input.
        history: list of prior messages (each {'role': ..., 'content': ...}).
                 Pass the value returned in 'history' from the previous chat() call.
        client: optional Anthropic client; one is created if omitted.

    Returns:
        {
          'reply':       final assistant text,
          'tool_calls':  [{'tool', 'input', 'output'}, ...] for breadcrumbs,
          'history':     full message list including this turn (round-trip-safe).
        }
    """
    client = client or Anthropic()
    history = list(history or [])
    messages = history + [{'role': 'user', 'content': user_message}]

    breadcrumbs = []
    final_resp = None
    system = _build_system_prompt()

    for _ in range(MAX_TOOL_ITERATIONS):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        final_resp = resp

        # Convert assistant content blocks to dicts so they round-trip via JSON
        # (Streamlit session_state handles objects too, but dicts are safer).
        assistant_content = []
        tool_uses = []
        for block in resp.content:
            if block.type == 'text':
                assistant_content.append({'type': 'text', 'text': block.text})
            elif block.type == 'tool_use':
                tu = {'type': 'tool_use', 'id': block.id, 'name': block.name, 'input': block.input}
                assistant_content.append(tu)
                tool_uses.append(tu)
        messages.append({'role': 'assistant', 'content': assistant_content})

        if resp.stop_reason != 'tool_use' or not tool_uses:
            break

        tool_results = []
        for tu in tool_uses:
            fn = _TOOL_DISPATCH.get(tu['name'])
            try:
                output = fn(tu['input']) if fn else {'error': f'Unknown tool: {tu["name"]}'}
            except ValueError as e:
                output = {'error': str(e)}
            except Exception as e:
                output = {'error': f'{type(e).__name__}: {e}'}

            breadcrumbs.append({'tool': tu['name'], 'input': tu['input'], 'output': output})

            payload = json.dumps(output, default=str)
            if len(payload) > TOOL_RESULT_CHAR_CAP:
                payload = payload[:TOOL_RESULT_CHAR_CAP] + '... (truncated)'

            tool_results.append({
                'type': 'tool_result',
                'tool_use_id': tu['id'],
                'content': payload,
            })

        messages.append({'role': 'user', 'content': tool_results})

    # Extract the final assistant text
    reply_chunks = []
    if final_resp is not None:
        for block in final_resp.content:
            if block.type == 'text' and block.text:
                reply_chunks.append(block.text)
    reply = '\n'.join(reply_chunks).strip() or '(no text response)'

    return {'reply': reply, 'tool_calls': breadcrumbs, 'history': messages}


# ── CLI (kept for backward compat) ────────────────────────────────────────────
def main():
    print("=" * 60)
    print("PROCUREMENT ANALYTICS AGENT v4.0 — Tool-Calling")
    print("Multi-Warehouse: P9 + 21C")
    print("=" * 60)

    if not os.path.exists(DB_PATH):
        print(f"❌ {DB_PATH} not found. Run: python prepare_data_final.py")
        return

    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ ANTHROPIC_API_KEY not set in environment / .env")
        return

    print("\nType 'exit' to quit. Conversation has memory within this session.\n")
    client = Anthropic()
    history = []

    while True:
        user = input("\n💬 You: ").strip()
        if user.lower() in ('exit', 'quit', 'q'):
            break
        if not user:
            continue
        try:
            result = chat(user, history, client=client)
            history = result['history']
            for tc in result['tool_calls']:
                preview = json.dumps(tc['input'])[:80]
                print(f"  [{tc['tool']}({preview})]")
            print(f"\n🤖 {result['reply']}")
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
