"""
Procurement Analytics Agent - REDESIGNED Dashboard (v4.0)
==========================================================
Dark "Mission Control" aesthetic:
  - Deep navy background
  - Electric teal & amber accents
  - Glassmorphism cards
  - Animated metrics
  - Multi-warehouse support
"""
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sqlite3, os, io, json
from datetime import datetime
from agent_expert import chat as agent_chat

DB_PATH = 'procurement_final.db'

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Procurement Command Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── DESIGN TOKENS ──────────────────────────────────────────────────────────────
C = {
    "bg":         "#080D18",
    "surface":    "#0E1623",
    "surface2":   "#14202F",
    "border":     "rgba(0,212,255,0.15)",
    "teal":       "#00D4FF",
    "teal_dim":   "rgba(0,212,255,0.10)",
    "amber":      "#F59E0B",
    "amber_dim":  "rgba(245,158,11,0.10)",
    "red":        "#EF4444",
    "red_dim":    "rgba(239,68,68,0.10)",
    "green":      "#10B981",
    "green_dim":  "rgba(16,185,129,0.10)",
    "purple":     "#8B5CF6",
    "purple_dim": "rgba(139,92,246,0.10)",
    "text":       "#94A3B8",
    "text_bright":"#F1F5F9",
    "mono":       "'DM Mono', 'Courier New', monospace",
    "sans":       "'Space Grotesk', sans-serif",
}

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&display=swap');

/* === RESET === */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stApp"],
.stApp, .main, section.main,
[data-testid="block-container"] {{
    background-color: {C['bg']} !important;
    color: {C['text']} !important;
    font-family: {C['sans']} !important;
}}

/* === SIDEBAR === */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {{
    background: {C['surface']} !important;
    border-right: 1px solid {C['border']} !important;
}}
[data-testid="stSidebar"] * {{ color: {C['text']} !important; font-family: {C['sans']} !important; }}

/* === HEADINGS === */
h1 {{
    font-family: {C['sans']} !important; font-size: 2rem !important;
    font-weight: 700 !important; color: {C['text_bright']} !important;
    letter-spacing: -0.03em !important; margin-bottom: .2rem !important;
}}
h2 {{
    font-family: {C['sans']} !important; font-size: 1.1rem !important;
    font-weight: 600 !important; color: {C['teal']} !important;
    letter-spacing: 0.08em !important; text-transform: uppercase !important;
}}
h3 {{ font-family: {C['sans']} !important; color: {C['text_bright']} !important; }}
p, span, div, label, li {{ color: {C['text']} !important; font-family: {C['sans']} !important; }}

/* === METRICS === */
[data-testid="metric-container"],
[data-testid="stMetric"] {{
    background: {C['surface']} !important;
    border: 1px solid {C['border']} !important;
    border-radius: 12px !important; padding: 1.1rem !important;
}}
[data-testid="stMetricValue"] {{
    font-family: {C['mono']} !important; font-size: 1.9rem !important;
    font-weight: 500 !important; color: {C['text_bright']} !important;
}}
[data-testid="stMetricLabel"] {{
    font-size: .72rem !important; text-transform: uppercase !important;
    letter-spacing: .07em !important; color: {C['text']} !important;
}}

/* === ALL BUTTONS — unified dark chip style === */
.stButton > button,
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"] {{
    background: {C['surface2']} !important;
    color: {C['teal']} !important;
    border: 1px solid {C['teal']}40 !important;
    font-weight: 500 !important; font-size: .82rem !important;
    border-radius: 8px !important; letter-spacing: 0 !important;
    font-family: {C['sans']} !important; box-shadow: none !important;
    cursor: pointer !important; pointer-events: auto !important;
    transition: background .2s ease !important;
}}
.stButton > button:hover,
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-secondary"]:hover {{
    background: {C['teal_dim']} !important;
    border-color: {C['teal']} !important;
    box-shadow: none !important;
}}

/* === INPUTS === */
[data-testid="stSelectbox"] > div > div,
.stTextArea textarea, .stTextInput input {{
    background: {C['surface2']} !important;
    border: 1px solid {C['border']} !important; border-radius: 8px !important;
    color: {C['text_bright']} !important; font-family: {C['sans']} !important;
}}
[data-testid="stSelectbox"] svg {{ fill: {C['teal']} !important; }}

/* === TABS === */
[data-baseweb="tab-list"] {{
    background: {C['surface']} !important; border-radius: 10px !important;
    padding: 5px !important; gap: 4px !important;
    border: 1px solid {C['border']} !important;
}}
[data-baseweb="tab"] {{
    background: transparent !important; color: {C['text']} !important;
    border-radius: 7px !important; font-family: {C['sans']} !important;
    font-weight: 500 !important; font-size: .88rem !important;
}}
[aria-selected="true"] {{
    background: {C['teal_dim']} !important; color: {C['teal']} !important;
    border: 1px solid {C['border']} !important;
}}

/* === DATAFRAME === */
[data-testid="stDataFrame"] {{
    border: 1px solid {C['border']} !important; border-radius: 12px !important;
}}
iframe {{ background: {C['surface']} !important; border-radius: 10px !important; }}

/* === EXPANDER === */
[data-testid="stExpander"] {{
    background: {C['surface']} !important; border: 1px solid {C['border']} !important;
    border-radius: 10px !important;
}}

/* === RADIO === */
[data-testid="stRadio"] label span {{ color: {C['text']} !important; }}

/* === SPINNER === */
[data-testid="stSpinner"] * {{ color: {C['teal']} !important; }}

/* === HIDE CHROME === */
#MainMenu, footer, header, [data-testid="stToolbar"] {{ visibility: hidden !important; }}

/* === HR === */
hr {{ border-color: {C['border']} !important; margin: 1.2rem 0 !important; }}

/* === SUCCESS / ERROR / WARNING / INFO === */
[data-testid="stAlert"] {{ border-radius: 10px !important; }}
</style>
""", unsafe_allow_html=True)

# ── PLOTLY BASE LAYOUT ─────────────────────────────────────────────────────────
def plotly_base(**kwargs):
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=C["text"], family="DM Mono, monospace", size=11),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.05)", color=C["text"]),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.05)", color=C["text"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=C["text"])),
        margin=dict(l=10, r=20, t=40, b=10),
        hoverlabel=dict(bgcolor=C["surface2"], font=dict(color=C["text_bright"])),
    )
    base.update(kwargs)
    return base

# ── HELPERS ────────────────────────────────────────────────────────────────────
def fmt(v):
    if pd.isna(v) or v == 0: return "₹0"
    if abs(v) >= 1e7: return f"₹{v/1e7:.2f}Cr"
    if abs(v) >= 1e5: return f"₹{v/1e5:.1f}L"
    return f"₹{v:,.0f}"

def q(sql):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(sql, conn); conn.close(); return df

def has_table(name):
    conn = sqlite3.connect(DB_PATH)
    t = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close(); return name in t

# ── UI COMPONENTS ──────────────────────────────────────────────────────────────
def stat_card(label, value, icon, accent="teal", sub=None):
    ac = C[accent]; ac_dim = C[f"{accent}_dim"]
    s = f"<div style='font-family:{C['mono']};font-size:.75rem;color:{C['text']};margin-top:.35rem'>{sub}</div>" if sub else ""
    st.markdown(f"""
    <div style='background:{C["surface"]};border:1px solid {ac}40;border-left:3px solid {ac};
                border-radius:12px;padding:1.1rem 1.3rem;height:110px;position:relative;overflow:hidden'>
        <div style='position:absolute;top:-8px;right:8px;font-size:3.2rem;opacity:0.07;user-select:none'>{icon}</div>
        <div style='font-size:.68rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
                    color:{C["text"]};margin-bottom:.35rem'>{label}</div>
        <div style='font-size:1.65rem;font-weight:700;font-family:{C["mono"]};color:{C["text_bright"]};line-height:1'>{value}</div>
        {s}
    </div>""", unsafe_allow_html=True)

def section_header(title, badge=None):
    b = (f"<span style='background:{C['teal_dim']};color:{C['teal']};font-size:.68rem;"
         f"padding:.2rem .65rem;border-radius:20px;border:1px solid {C['teal']}30;"
         f"font-family:{C['mono']};margin-left:.7rem'>{badge}</span>") if badge else ""
    st.markdown(f"""
    <div style='display:flex;align-items:center;margin:1.4rem 0 .9rem 0'>
        <div style='width:3px;height:1.1rem;background:{C["teal"]};border-radius:2px;margin-right:.75rem'></div>
        <span style='font-size:.95rem;font-weight:600;color:{C["text_bright"]}'>{title}</span>{b}
    </div>""", unsafe_allow_html=True)

def alert_box(msg, kind="info"):
    cfg = {
        "critical": (C["red"],   C["red_dim"],    "🚨"),
        "warning":  (C["amber"], C["amber_dim"],  "⚠️"),
        "info":     (C["teal"],  C["teal_dim"],   "ℹ️"),
        "ok":       (C["green"], C["green_dim"],  "✅"),
    }
    ac, bg, icon = cfg.get(kind, cfg["info"])
    st.markdown(f"""
    <div style='background:{bg};border:1px solid {ac}40;border-radius:10px;
                padding:.85rem 1.1rem;margin:.4rem 0;display:flex;align-items:flex-start;gap:.75rem'>
        <span style='font-size:1rem'>{icon}</span>
        <span style='color:{ac};font-size:.88rem'>{msg}</span>
    </div>""", unsafe_allow_html=True)

def dark_hbar(df, x_col, y_col, palette=None, height=320, title=None):
    p = palette or [C["teal"], C["amber"], C["purple"], C["green"], C["red"]]
    colors = [p[i % len(p)] for i in range(len(df))]
    fig = go.Figure(go.Bar(
        x=df[x_col], y=df[y_col], orientation='h',
        text=df[x_col], textposition='outside',
        marker=dict(color=colors, opacity=0.82, line=dict(width=0)),
        textfont=dict(color=C["text"], size=10),
    ))
    kw = dict(title=dict(text=title, font=dict(size=12, color=C["text"]))) if title else {}
    fig.update_layout(**plotly_base(height=height, **kw))
    return fig

def dark_bar(df, x_col, y_col, colors=None, text=None, height=300, title=None):
    c = colors or C["teal"]
    bar_text = text if text is not None else df[y_col].tolist()
    fig = go.Figure(go.Bar(
        x=df[x_col], y=df[y_col],
        text=bar_text,
        textposition='outside',
        marker=dict(color=c, opacity=0.82, line=dict(width=0)),
        textfont=dict(color=C["text"], size=10),
    ))
    kw = dict(title=dict(text=title, font=dict(size=12, color=C["text"]))) if title else {}
    fig.update_layout(**plotly_base(height=height, **kw))
    return fig

def dark_group_bar(df, x_col, y_cols, names, colors, height=320, title=None):
    fig = go.Figure()
    for y, name, color in zip(y_cols, names, colors):
        fig.add_trace(go.Bar(name=name, x=df[x_col], y=df[y], marker_color=color, opacity=0.82))
    kw = dict(title=dict(text=title, font=dict(size=12, color=C["text"]))) if title else {}
    fig.update_layout(**plotly_base(barmode='group', height=height,
                                    legend=dict(orientation='h', y=1.12), **kw))
    return fig

def dark_treemap(df, path, values, color, color_map=None, title=None, height=420):
    fig = px.treemap(df, path=path, values=values, color=color, color_discrete_map=color_map)
    fig.update_traces(
        textfont=dict(color=C["text_bright"], family="DM Mono, monospace", size=11),
        marker=dict(line=dict(color=C["bg"], width=2)),
        hovertemplate='<b>%{label}</b><br>Value: %{value:,.0f}<br>%{percentParent} of parent<extra></extra>',
    )
    kw = dict(title=dict(text=title, font=dict(size=12, color=C["text"]))) if title else {}
    fig.update_layout(**plotly_base(height=height, margin=dict(l=10, r=10, t=40, b=10), **kw))
    return fig

def dark_donut(df, values, names, title=None, height=300):
    palette = [C["teal"], C["amber"], C["purple"], C["green"], C["red"]]
    fig = go.Figure(go.Pie(
        labels=df[names], values=df[values], hole=0.55,
        marker=dict(colors=palette[:len(df)], line=dict(color=C["bg"], width=3)),
        textinfo='label+percent', textfont=dict(color=C["text_bright"], size=11),
        hoverinfo='label+value',
    ))
    kw = dict(title=dict(text=title, font=dict(size=12, color=C["text"]))) if title else {}
    fig.update_layout(**plotly_base(height=height, showlegend=False, **kw))
    return fig

# ── AGENT (tool-calling, in agent_expert.py) ───────────────────────────────────
# Replaced the LangChain SQL toolkit with a native Anthropic tool-calling loop.
# Conversation memory and tool dispatch happen in agent_expert.chat().
HISTORY_TURN_CAP = 20  # trim chat memory to last N user/assistant turns

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def sidebar():
    with st.sidebar:
        st.markdown(f"""
        <div style='padding:1rem 0 1.2rem 0;border-bottom:1px solid {C["border"]};margin-bottom:1.2rem'>
            <div style='font-size:1.1rem;font-weight:700;color:{C["text_bright"]};letter-spacing:-.02em;line-height:1.3'>
                ⚡ Procurement<br>Command Center
            </div>
            <div style='font-size:.7rem;color:{C["text"]};margin-top:.4rem;font-family:{C["mono"]}'>
                Multi-Warehouse Analytics v4.0
            </div>
        </div>""", unsafe_allow_html=True)

        page = st.radio("NAV", [
            "🏠  Overview",
            "🎯  Optimization",
            "📦  Inventory",
            "🔮  Forecast & SS",
            "🤖  AI Assistant",
        ], label_visibility="collapsed")

        # live stats
        if os.path.exists(DB_PATH) and has_table('planning_master'):
            qs = q("SELECT COUNT(*) as n, COALESCE(SUM(stock_value),0) as sv, SUM(is_critical) as crit FROM planning_master").iloc[0]
            n_wh = q("SELECT COUNT(DISTINCT warehouse) as n FROM planning_master").iloc[0]['n']
            st.markdown(f"""
            <div style='margin-top:1.5rem;padding:1rem;background:{C["surface2"]};border-radius:10px;border:1px solid {C["border"]}'>
                <div style='font-size:.65rem;color:{C["text"]};letter-spacing:.1em;text-transform:uppercase;margin-bottom:.8rem'>Live Snapshot</div>
                {''.join([f'<div style="display:flex;justify-content:space-between;margin-bottom:.45rem"><span style="font-size:.8rem;color:{C["text"]}">{k}</span><span style="font-family:{C["mono"]};font-size:.8rem;color:{vc}">{vv}</span></div>' for k, vv, vc in [("Warehouses", str(int(n_wh)), C["teal"]), ("Materials", f"{int(qs['n']):,}", C["text_bright"]), ("Stock Value", fmt(qs['sv']), C["teal"]), ("Critical 🚨", str(int(qs['crit'])), C["red"])]])}
            </div>""", unsafe_allow_html=True)

        warehouses = q("SELECT DISTINCT warehouse FROM planning_master ORDER BY warehouse")['warehouse'].tolist() if os.path.exists(DB_PATH) and has_table('planning_master') else []
        wh_pills = " ".join([f"<span style='background:{[C['teal'],C['amber']][i%2]}20;color:{[C['teal'],C['amber']][i%2]};border:1px solid {[C['teal'],C['amber']][i%2]}40;border-radius:20px;padding:.15rem .6rem;font-size:.7rem;font-family:{C['mono']};display:inline-block;margin:.15rem'>{wh}</span>" for i,wh in enumerate(warehouses)])
        if wh_pills:
            st.markdown(f"<div style='margin-top:1rem'>{wh_pills}</div>", unsafe_allow_html=True)

        st.markdown(f"""
        <div style='position:absolute;bottom:1.2rem;left:1.2rem;right:1.2rem'>
            <div style='font-size:.65rem;color:{C["text"]};font-family:{C["mono"]};line-height:1.7'>
                Powered by Artificial Intelligence· Ayush<br>
                <span style='color:{C["green"]}'>●</span> Connected · {datetime.now().strftime('%H:%M, %d %b %Y')}
            </div>
        </div>""", unsafe_allow_html=True)

    return page

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
def page_overview():
    st.markdown(f"""
    <h1>Procurement Overview</h1>
    <p style='color:{C["text"]};font-family:{C["mono"]};font-size:.78rem;margin-bottom:1.2rem'>
        {datetime.now().strftime('%A, %d %B %Y')} &nbsp;·&nbsp; Real-time Intelligence
    </p>""", unsafe_allow_html=True)

    warehouses = q("SELECT DISTINCT warehouse FROM planning_master ORDER BY warehouse")['warehouse'].tolist() if has_table('planning_master') else []
    col_f, _ = st.columns([3,7])
    with col_f:
        sel = st.selectbox("", ["All Warehouses"] + warehouses,
                            format_func=lambda x: f"🏭  {x}",
                            label_visibility="collapsed", key="ov_wh")
    wf     = f"WHERE warehouse='{sel}'" if sel != "All Warehouses" else ""
    wf_and = f"AND warehouse='{sel}'"   if sel != "All Warehouses" else ""

    if not has_table('planning_master'):
        alert_box("Database not found. Run `python prepare_data_final.py` first.", "critical")
        return

    s = q(f"""SELECT COUNT(*) as n,
                   COALESCE(SUM(stock_value),0) as sv,
                   COALESCE(SUM(order_amount),0) as tbo,
                   COALESCE(SUM(pending_order_value),0) as pend,
                   COALESCE(SUM(allocation_value),0) as alloc,
                   SUM(CASE WHEN safety_stock_gap<0 THEN 1 ELSE 0 END) as below,
                   SUM(is_critical) as crit,
                   COUNT(DISTINCT supplier_name) as sups
            FROM planning_master {wf}""").iloc[0]

    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
    r1 = st.columns(4)
    with r1[0]: stat_card("STOCK VALUE",     fmt(s['sv']),   "📦", "teal")
    with r1[1]: stat_card("TO BE ORDERED",   fmt(s['tbo']),  "🛒", "amber", sub=f"{int(q(f'SELECT COUNT(*) as n FROM planning_master WHERE tbo_qty>0 {wf_and}').iloc[0][0]):,} materials")
    with r1[2]: stat_card("PENDING ORDERS",  fmt(s['pend']), "🔄", "purple")
    with r1[3]: stat_card("ALLOCATIONS",     fmt(s['alloc']),"🎯", "green")

    st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
    comp = round((1 - s['below']/s['n'])*100,1) if s['n']>0 else 0
    tbo_rt = round(s['tbo']/s['sv']*100,1) if s['sv']>0 else 0

    r2 = st.columns(4)
    with r2[0]: stat_card("SS COMPLIANCE",   f"{comp}%",          "🛡️", "green" if comp>80 else "amber" if comp>60 else "red", sub=f"{int(s['below'])} below target")
    with r2[1]: stat_card("CRITICAL",        f"{int(s['crit'])}", "🚨", "red",    sub="No TBO + below safety")
    with r2[2]: stat_card("MATERIALS",       f"{int(s['n']):,}",  "📊", "teal",  sub=f"{int(s['sups'])} active suppliers")
    with r2[3]: stat_card("TBO / STOCK",     f"{tbo_rt}%",        "📈", "amber", sub="Order pressure ratio")

    st.markdown("---")

    # ── Charts ──
    if sel == "All Warehouses" and len(warehouses) > 1:
        section_header("Warehouse Performance Comparison")
        wh = q("""SELECT warehouse,
                         ROUND(SUM(stock_value),0) as stock_v,
                         ROUND(SUM(order_amount),0) as tbo_v,
                         ROUND(SUM(pending_order_value),0) as pend_v,
                         SUM(CASE WHEN safety_stock_gap<0 THEN 1 ELSE 0 END) as below_s,
                         SUM(is_critical) as crit,
                         COUNT(DISTINCT supplier_name) as sups
                  FROM planning_master GROUP BY warehouse""")

        c1, c2 = st.columns(2)
        with c1:
            fig = dark_group_bar(wh, 'warehouse',
                ['stock_v','tbo_v','pend_v'],
                ['Stock','TBO','Pending'],
                [C['teal'],C['amber'],C['purple']],
                height=310, title="Financial Overview by Warehouse")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = dark_group_bar(wh, 'warehouse',
                ['below_s','crit','sups'],
                ['Below Safety','Critical','Suppliers'],
                [C['amber'],C['red'],C['green']],
                height=310, title="Risk & Supplier Metrics by Warehouse")
            st.plotly_chart(fig, use_container_width=True)

        # Scorecard
        wh_show = wh.copy()
        wh_show['Stock Value']    = wh_show['stock_v'].apply(fmt)
        wh_show['TBO']            = wh_show['tbo_v'].apply(fmt)
        wh_show['Pending']        = wh_show['pend_v'].apply(fmt)
        wh_show['Below Safety']   = wh_show['below_s'].astype(int)
        wh_show['Critical 🚨']    = wh_show['crit'].astype(int)
        wh_show['Suppliers']      = wh_show['sups'].astype(int)
        st.dataframe(wh_show[['warehouse','Stock Value','TBO','Pending','Below Safety','Critical 🚨','Suppliers']].rename(columns={'warehouse':'Warehouse'}),
                     use_container_width=True, hide_index=True)

    # ── Alerts ──
    st.markdown("---")
    section_header("Action Required")
    a1,a2,a3 = st.columns(3)
    with a1:
        if s['crit']>0: alert_box(f"<b>{int(s['crit'])} critical materials</b> — below safety stock with no purchase order. Production risk!", "critical")
        else:           alert_box("All shortages have purchase orders placed. Good!", "ok")
    with a2:
        n_tbo = int(q(f"SELECT COUNT(*) as n FROM planning_master WHERE tbo_qty>0 {wf_and}").iloc[0][0])
        alert_box(f"<b>{n_tbo} materials</b> queued for ordering — {fmt(s['tbo'])} total. Review and approve.", "warning")
    with a3:
        alert_box(f"<b>{fmt(s['pend'])}</b> in pending orders pipeline. Track lead times and expected deliveries.", "info")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — OPTIMIZATION
# ══════════════════════════════════════════════════════════════════════════════
def page_optimization():
    st.markdown(f"""
    <h1>Optimization Hub</h1>
    <p style='color:{C["text"]};font-family:{C["mono"]};font-size:.78rem;margin-bottom:1.2rem'>
        Critical materials · TBO orders · Pending pipeline · Supplier intelligence
    </p>""", unsafe_allow_html=True)

    warehouses = q("SELECT DISTINCT warehouse FROM planning_master ORDER BY warehouse")['warehouse'].tolist() if has_table('planning_master') else []
    col_f, _ = st.columns([3,7])
    with col_f:
        sel = st.selectbox("", ["All Warehouses"] + warehouses,
                            format_func=lambda x: f"🏭  {x}",
                            label_visibility="collapsed", key="opt_wh")
    wf_and = f"AND warehouse='{sel}'" if sel != "All Warehouses" else ""
    wf_where = f"WHERE warehouse='{sel}'" if sel != "All Warehouses" else ""

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["🚨  Critical", "🛒  TBO Orders", "🔄  Pending", "🏢  Suppliers", "🛡️  Supplier Risk"]
    )

    with tab1:
        n_crit = int(q(f"SELECT COUNT(*) as n FROM planning_master WHERE is_critical=1 {wf_and}").iloc[0][0])
        section_header("Below Safety Stock + No Purchase Order Placed", badge=str(n_crit))
        crit = q(f"""SELECT warehouse, material_code, description,
                            ROUND(current_stock,0) as stock,
                            ROUND(safety_stock,0) as safety,
                            ROUND(safety_stock_gap,0) as gap,
                            supplier_name
                     FROM planning_master WHERE is_critical=1 {wf_and}
                     ORDER BY safety_stock_gap ASC LIMIT 60""")
        if len(crit)>0:
            alert_box(f"<b>{len(crit)} materials</b> need immediate purchase orders. Each day of delay increases production stoppage risk.", "critical")
            st.dataframe(crit, use_container_width=True, hide_index=True,
                column_config={
                    "warehouse": st.column_config.TextColumn("WH", width="small"),
                    "material_code": "Code",
                    "description": st.column_config.TextColumn("Description", width="large"),
                    "stock":   st.column_config.NumberColumn("Stock",       format="%.0f"),
                    "safety":  st.column_config.NumberColumn("Safety Stock", format="%.0f"),
                    "gap":     st.column_config.NumberColumn("Gap",          format="%.0f"),
                    "supplier_name": "Supplier",
                })
        else:
            alert_box("No critical materials found. All shortages have orders placed!", "ok")

    with tab2:
        tbo = q(f"""SELECT warehouse, material_code, description,
                           ROUND(tbo_qty,0) as tbo_qty,
                           ROUND(order_amount,2) as order_value,
                           ROUND(unit_price,2) as unit_price,
                           ROUND(safety_stock_gap,0) as ss_gap,
                           supplier_name
                    FROM planning_master WHERE tbo_qty>0 {wf_and}
                    ORDER BY order_amount DESC LIMIT 60""")
        total_tbo = q(f"SELECT COALESCE(SUM(order_amount),0) as v FROM planning_master WHERE tbo_qty>0 {wf_and}").iloc[0]['v']

        section_header("Materials To Be Ordered", badge=f"{len(tbo)} materials · {fmt(total_tbo)}")
        c1,c2,c3 = st.columns(3)
        with c1: stat_card("TOTAL TBO VALUE",  fmt(total_tbo), "🛒", "amber")
        with c2: stat_card("MATERIALS",        str(len(tbo)), "📋", "teal")
        with c3: stat_card("AVG ORDER SIZE",   fmt(total_tbo/len(tbo)) if len(tbo)>0 else "₹0", "📊", "purple")

        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

        # TBO by supplier chart
        tbo_sup = q(f"""SELECT supplier_name, ROUND(SUM(order_amount),0) as val
                        FROM planning_master WHERE tbo_qty>0 {wf_and} AND supplier_name IS NOT NULL
                        GROUP BY supplier_name ORDER BY val DESC LIMIT 10""")
        if len(tbo_sup)>0:
            section_header("TBO by Supplier", badge="Top 10")
            fig = dark_hbar(tbo_sup, 'val', 'supplier_name', height=300)
            st.plotly_chart(fig, use_container_width=True)

        section_header("All TBO Materials")
        st.dataframe(tbo, use_container_width=True, hide_index=True,
            column_config={
                "warehouse":    st.column_config.TextColumn("WH", width="small"),
                "material_code":"Code",
                "description":  st.column_config.TextColumn("Description", width="large"),
                "tbo_qty":      st.column_config.NumberColumn("TBO Qty",     format="%.0f"),
                "order_value":  st.column_config.NumberColumn("Order Value ₹",format="%.2f"),
                "unit_price":   st.column_config.NumberColumn("Unit Price",   format="%.2f"),
                "ss_gap":       st.column_config.NumberColumn("SS Gap",       format="%.0f"),
                "supplier_name":"Supplier",
            })

        st.markdown(f"""
        <div style='background:{C["teal_dim"]};border:1px solid {C["teal"]}30;border-radius:10px;
                    padding:.9rem 1.1rem;margin-top:.8rem;font-family:{C["mono"]};font-size:.82rem'>
            <b style='color:{C["teal"]}'>TBO Formula</b>&nbsp;&nbsp;
            TBO = Safety Stock − (Current Stock + Pending Orders − Allocations)<br>
            <span style='color:{C["text"]};font-size:.75rem'>Enhanced: ROP = (Lead Time × Daily Demand) + Safety Stock</span>
        </div>""", unsafe_allow_html=True)

    with tab3:
        pend_wf = f"WHERE warehouse='{sel}'" if sel != "All Warehouses" else ""
        pend = q(f"""SELECT warehouse, material_code, description,
                            ROUND(pending_order_qty,0) as qty,
                            ROUND(pending_order_value,2) as value,
                            supplier_name
                     FROM pending_orders {pend_wf}
                     ORDER BY pending_order_value DESC LIMIT 60""")
        total_pend = pend['value'].sum() if len(pend)>0 else 0

        section_header("Pending Orders Pipeline", badge=f"{len(pend)} orders · {fmt(total_pend)}")
        if len(pend)>0:
            c1,c2,c3 = st.columns(3)
            with c1: stat_card("PIPELINE VALUE",   fmt(total_pend), "🔄", "purple")
            with c2: stat_card("ORDERS",           str(len(pend)),  "📬", "teal")
            with c3: stat_card("WAREHOUSES",       str(pend['warehouse'].nunique()), "🏭", "amber")
            st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
            st.dataframe(pend, use_container_width=True, hide_index=True,
                column_config={
                    "warehouse":    st.column_config.TextColumn("WH", width="small"),
                    "material_code":"Code",
                    "description":  st.column_config.TextColumn("Description", width="large"),
                    "qty":          st.column_config.NumberColumn("Pending Qty", format="%.0f"),
                    "value":        st.column_config.NumberColumn("Value ₹",     format="%.2f"),
                    "supplier_name":"Supplier",
                })
        else:
            alert_box("No pending orders found.", "info")

    with tab4:
        section_header("Supplier Intelligence")
        if has_table('supplier_master'):
            # When a warehouse is selected, query planning_master for that warehouse's suppliers
            if sel != "All Warehouses":
                sup = q(f"""SELECT supplier_name,
                                   COUNT(*) as material_count,
                                   '{sel}' as warehouses,
                                   ROUND(SUM(order_amount),0) as order_val,
                                   ROUND(AVG(lead_time_weeks),1) as lead_wks
                            FROM planning_master
                            WHERE warehouse='{sel}' AND supplier_name IS NOT NULL
                            GROUP BY supplier_name
                            ORDER BY material_count DESC LIMIT 30""")
                tot_sups = len(sup)
                multi_n  = 0
                tot_val  = sup['order_val'].sum()
            else:
                sup = q("SELECT supplier_name, material_count, warehouses, ROUND(total_order_value,0) as order_val, ROUND(avg_lead_time_weeks,1) as lead_wks FROM supplier_master ORDER BY material_count DESC LIMIT 30")
                tot_sups = int(q("SELECT COUNT(*) as n FROM supplier_master").iloc[0]['n'])
                multi_n  = int(q("SELECT COUNT(*) as n FROM supplier_master WHERE warehouse_count>1").iloc[0]['n'])
                tot_val  = q("SELECT COALESCE(SUM(total_order_value),0) as v FROM supplier_master").iloc[0]['v']

            c1,c2,c3 = st.columns(3)
            with c1: stat_card("SUPPLIERS",          str(tot_sups), "🏢", "teal",
                                sub=f"in {sel}" if sel != "All Warehouses" else "across all warehouses")
            with c2: stat_card("MULTI-WH SUPPLIERS", str(multi_n),  "🔗", "amber",
                                sub="Consolidation opportunity" if sel == "All Warehouses" else "N/A for single WH")
            with c3: stat_card("TOTAL ORDER VALUE",  fmt(tot_val),  "💰", "green")

            st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
            section_header(f"Top Suppliers — {sel}")
            fig = dark_hbar(sup.head(10), 'material_count', 'supplier_name', height=330)
            st.plotly_chart(fig, use_container_width=True)

            if sel == "All Warehouses":
                multi = q("SELECT supplier_name, material_count, warehouses, ROUND(total_order_value,0) as order_val FROM supplier_master WHERE warehouse_count>1 ORDER BY material_count DESC")
                if len(multi)>0:
                    section_header("Multi-Warehouse Suppliers", badge="Consolidation Targets")
                    alert_box(f"<b>{len(multi)} suppliers</b> serve multiple warehouses — consolidate orders for better pricing.", "info")
                    st.dataframe(multi, use_container_width=True, hide_index=True)

            section_header("All Suppliers")
            st.dataframe(sup, use_container_width=True, hide_index=True,
                column_config={
                    "supplier_name":  "Supplier Name",
                    "material_count": st.column_config.NumberColumn("Materials", format="%d"),
                    "warehouses":     "Warehouses",
                    "order_val":      st.column_config.NumberColumn("Order Value ₹", format="%.0f"),
                    "lead_wks":       st.column_config.NumberColumn("Lead (wks)", format="%.1f"),
                })

    with tab5:
        if not has_table('supplier_risk'):
            alert_box("Supplier risk table not built. Re-run <code>python prepare_data_final.py</code>.", "warning")
        else:
            risk = q("SELECT * FROM supplier_risk ORDER BY risk_score DESC")
            if risk.empty:
                alert_box("No suppliers found in risk analysis.", "info")
            else:
                tier_counts = risk['risk_tier'].value_counts().to_dict()
                c1, c2, c3, c4 = st.columns(4)
                with c1: stat_card("CRITICAL",  str(tier_counts.get('Critical', 0)), "🚨", "red",
                                    sub="Diversify urgently")
                with c2: stat_card("HIGH RISK", str(tier_counts.get('High', 0)),     "⚠️", "amber",
                                    sub="Review & monitor")
                with c3: stat_card("SINGLE-SOURCE A", str(int(risk['single_source_a_count'].sum())),
                                    "🎯", "purple", sub="Sole-supplied A-class items")
                with c4: stat_card("TOP-5 SPEND %", f"{risk.head(5)['spend_pct'].sum():.0f}%",
                                    "💰", "teal", sub="Concentration in top suppliers")

                st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

                section_header("Spend Concentration Treemap", badge="Coloured by risk tier")
                tier_colors = {
                    'Critical': C['red'], 'High': C['amber'],
                    'Medium':   C['teal'], 'Low':  C['green'],
                }
                tree_df = risk[risk['spend_value'] > 0].copy()
                if not tree_df.empty:
                    fig = dark_treemap(
                        tree_df, path=['risk_tier', 'supplier_name'],
                        values='spend_value', color='risk_tier',
                        color_map=tier_colors, height=440,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                section_header("Top 15 Highest-Risk Suppliers")
                top_risk = risk.head(15)[[
                    'supplier_name', 'risk_tier', 'risk_score', 'spend_pct',
                    'single_source_a_count', 'lt_std_weeks', 'warehouse_count', 'material_count',
                ]].copy()
                top_risk['spend_pct'] = top_risk['spend_pct'].round(1)
                st.dataframe(top_risk, use_container_width=True, hide_index=True,
                    column_config={
                        'supplier_name':         'Supplier',
                        'risk_tier':             st.column_config.TextColumn('Tier', width='small'),
                        'risk_score':            st.column_config.NumberColumn('Risk Score', format='%.1f'),
                        'spend_pct':             st.column_config.NumberColumn('Spend %', format='%.1f%%'),
                        'single_source_a_count': st.column_config.NumberColumn('Sole-Source A', format='%d'),
                        'lt_std_weeks':          st.column_config.NumberColumn('LT σ (wks)', format='%.1f'),
                        'warehouse_count':       st.column_config.NumberColumn('# WH', format='%d', width='small'),
                        'material_count':        st.column_config.NumberColumn('# Items', format='%d'),
                    })

                # Single-source A-class exposures (the actionable list)
                ss_a = q("""
                    SELECT pm.supplier_name, pm.material_code, pm.description,
                           sm.abc_class, ROUND(pm.order_amount + COALESCE(pm.pending_order_value,0), 0) as open_value,
                           pm.warehouse
                    FROM planning_master pm
                    LEFT JOIN stock_master sm USING(material_code)
                    WHERE sm.abc_class = 'A'
                      AND pm.supplier_name IS NOT NULL
                      AND pm.material_code IN (
                            SELECT material_code FROM planning_master
                            WHERE supplier_name IS NOT NULL
                            GROUP BY material_code HAVING COUNT(DISTINCT supplier_name) = 1
                      )
                    ORDER BY open_value DESC
                """)
                if not ss_a.empty:
                    section_header("Single-Source A-Class Exposures",
                                   badge=f"{len(ss_a)} materials · {fmt(ss_a['open_value'].sum())}")
                    alert_box(f"<b>{len(ss_a)} A-class materials</b> have only one supplier in the planning data. Any disruption affects production directly.", "warning")
                    st.dataframe(ss_a.head(50), use_container_width=True, hide_index=True,
                        column_config={
                            'supplier_name': 'Supplier',
                            'material_code': 'Code',
                            'description':   st.column_config.TextColumn('Description', width='large'),
                            'abc_class':     st.column_config.TextColumn('ABC', width='small'),
                            'open_value':    st.column_config.NumberColumn('Open Value ₹', format='%.0f'),
                            'warehouse':     st.column_config.TextColumn('WH', width='small'),
                        })

                st.markdown(f"""
                <div style='background:{C["surface"]};border:1px solid {C["border"]};border-radius:10px;
                            padding:.9rem 1.1rem;margin-top:.8rem;font-family:{C["mono"]};font-size:.78rem;color:{C["text"]}'>
                    <b style='color:{C["teal"]}'>Risk Score Formula</b>&nbsp;&nbsp;
                    40% Single-source A-class · 30% Spend concentration · 20% Lead-time variance · 10% Coverage<br>
                    Each factor normalised to its population maximum, then weighted. Re-baselined on every database rebuild.
                </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — INVENTORY
# ══════════════════════════════════════════════════════════════════════════════
def page_inventory():
    st.markdown(f"""
    <h1>Inventory Overview</h1>
    <p style='color:{C["text"]};font-family:{C["mono"]};font-size:.78rem;margin-bottom:1.2rem'>
        All plants · 419 AT · 419 PD · 21C · P9 · Stock as on 31-Mar-2026
    </p>""", unsafe_allow_html=True)

    if not has_table('stock_master'):
        alert_box("Stock status data not loaded. Place <b>STOCK STATUS DT 31.03.2026.xlsx</b> in Data/ folder and re-run prepare_data_final.py.", "warning")
        if has_table('planning_master'):
            section_header("Planning Data Fallback (P9 + 21C)")
            df = q("SELECT warehouse as Warehouse, COUNT(*) as Materials, ROUND(SUM(stock_value),0) as 'Stock Value' FROM planning_master GROUP BY warehouse")
            df['Stock Value'] = df['Stock Value'].apply(fmt)
            st.dataframe(df, use_container_width=True, hide_index=True)
        return

    s = q("""SELECT COUNT(*) as n, COALESCE(SUM(total_stock_value),0) as val,
                    COALESCE(SUM(excess_stock_value),0) as excess,
                    COALESCE(AVG(CASE WHEN total_stock_qty>0 THEN days_of_inventory END),0) as doi,
                    COALESCE(AVG(CASE WHEN total_stock_qty>0 THEN inventory_turnover_ratio END),0) as itr
             FROM stock_master""").iloc[0]

    c1,c2,c3,c4 = st.columns(4)
    with c1: stat_card("TOTAL INVENTORY",  fmt(s['val']),        "🏦", "teal")
    with c2: stat_card("EXCESS INVENTORY", fmt(s['excess']),     "⚠️", "amber", sub="Can be freed up")
    with c3: stat_card("DAYS OF INVENTORY",f"{s['doi']:.0f}d",   "📅", "green", sub="Target: 30-45d")
    with c4: stat_card("TURNOVER RATIO",   f"{s['itr']:.1f}x",   "🔄", "purple", sub="Target: 8-12x")

    st.markdown("---")

    if has_table('stock_by_location'):
        section_header("Stock Distribution by Plant")
        loc = q("SELECT plant_code, COUNT(DISTINCT material_code) as mats, ROUND(SUM(stock_value),0) as val FROM stock_by_location GROUP BY plant_code ORDER BY val DESC")
        c1,c2 = st.columns(2)
        with c1:
            fig = dark_donut(loc, 'val', 'plant_code', title="By Value", height=310)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = dark_bar(loc, 'plant_code', 'val',
                colors=[C['teal'],C['amber'],C['purple'],C['green']],
                text=[fmt(v) for v in loc['val']],
                height=310, title="Stock Value by Plant")
            st.plotly_chart(fig, use_container_width=True)

    if 'abc_class' in q("SELECT * FROM stock_master LIMIT 1").columns:
        st.markdown("---")
        section_header("ABC Classification")
        abc = q("SELECT abc_class, COUNT(*) as count, ROUND(SUM(total_stock_value),0) as val FROM stock_master GROUP BY abc_class ORDER BY abc_class")
        abc_c = {r['abc_class']: [C['red'],C['amber'],C['teal']][i] for i,r in abc.iterrows()}
        c1,c2 = st.columns(2)
        with c1:
            fig = dark_bar(abc, 'abc_class', 'val',
                colors=[abc_c.get(c, C['teal']) for c in abc['abc_class']],
                text=[fmt(v) for v in abc['val']], height=280, title="Value by Class")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = dark_bar(abc, 'abc_class', 'count',
                colors=[abc_c.get(c, C['teal']) for c in abc['abc_class']],
                text=abc['count'], height=280, title="Count by Class")
            st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — FORECAST & SAFETY STOCK OPTIMIZER
# ══════════════════════════════════════════════════════════════════════════════
def page_forecast():
    st.markdown(f"""
    <h1>Forecast & SS Optimizer</h1>
    <p style='color:{C["text"]};font-family:{C["mono"]};font-size:.78rem;margin-bottom:1.2rem'>
        Right-size safety stock against your chosen service level · ₹ release vs. shortfall · 3-yr demand trend
    </p>""", unsafe_allow_html=True)

    if not has_table('stock_master'):
        alert_box("Stock master not loaded. Run <code>python prepare_data_final.py</code> after placing source Excel files in Data/.", "critical")
        return

    cols_present = q("SELECT * FROM stock_master LIMIT 1").columns.tolist()
    required = ['safety_stock_optimal_95', 'safety_stock_optimal_98', 'safety_stock_optimal_99',
                'forecast_next_year', 'safety_stock_hist', 'avg_muac_rate']
    missing = [c for c in required if c not in cols_present]
    if missing:
        alert_box(f"Forecast columns not found in stock_master: <code>{', '.join(missing)}</code>. Re-run <code>python prepare_data_final.py</code> to rebuild the database.", "warning")
        return

    # ── Filters ───────────────────────────────────────────────────────────
    cf1, cf2 = st.columns([2, 5])
    with cf1:
        sl_label = st.radio("Service Level", ["95%", "98%", "99%"],
                            index=1, horizontal=True, key="fc_sl")
    sl = int(sl_label.rstrip('%'))
    ss_col = f'safety_stock_optimal_{sl}'
    delta_col = f'ss_delta_value_{sl}'

    # ── Pull analyzable rows ──────────────────────────────────────────────
    df = q(f"""
        SELECT material_code, description,
               safety_stock_hist as ss_current,
               {ss_col} as ss_optimal,
               {delta_col} as delta_value,
               avg_annual_consumption, avg_daily_consumption,
               consumption_volatility, lead_time_days,
               avg_muac_rate, abc_class, xyz_class,
               fy_2022_23, fy_2023_24, fy_2024_25,
               forecast_next_year, forecast_lower_band, forecast_upper_band,
               total_stock_qty, total_stock_value
        FROM stock_master
        WHERE {ss_col} IS NOT NULL
          AND ss_current IS NOT NULL
    """)

    if df.empty:
        alert_box("No materials have enough data (lead time + 3-yr consumption) to compute optimal safety stock.", "warning")
        return

    df['delta_qty'] = df['ss_current'] - df['ss_optimal']
    over = df[df['delta_value'] > 0]
    under = df[df['delta_value'] < 0]

    # ── KPI strip ─────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1: stat_card("WORKING CAPITAL RELEASABLE", fmt(over['delta_value'].sum()),
                       "💰", "green", sub=f"{len(over)} overstocked items")
    with c2: stat_card("STOCKOUT RISK (₹)", fmt(abs(under['delta_value'].sum())),
                       "🚨", "red", sub=f"{len(under)} understocked items")
    with c3: stat_card("ITEMS ANALYZED", f"{len(df):,}",
                       "🔍", "teal", sub=f"of {q('SELECT COUNT(*) n FROM stock_master').iloc[0]['n']:,} total")
    with c4:
        z_lookup = {95: 1.645, 98: 2.054, 99: 2.326}
        stat_card(f"Z-SCORE @ {sl}%", f"{z_lookup[sl]:.3f}",
                  "📊", "purple", sub="Higher SL → more SS")

    st.markdown("---")

    # ── Top movers ────────────────────────────────────────────────────────
    section_header("Highest-Impact Items", badge=f"@ {sl}% service level")

    cL, cR = st.columns(2)
    with cL:
        st.markdown(f"<div style='font-size:.85rem;color:{C['green']};margin-bottom:.5rem'>"
                    f"💰 Top 10 Overstocked — SS can be cut</div>", unsafe_allow_html=True)
        top_over = over.nlargest(10, 'delta_value')[
            ['material_code', 'description', 'ss_current', 'ss_optimal', 'delta_value', 'abc_class', 'xyz_class']
        ].copy()
        top_over['delta_value'] = top_over['delta_value'].apply(fmt)
        top_over.columns = ['Code', 'Description', 'Current SS', 'Optimal SS', '₹ Releasable', 'ABC', 'XYZ']
        st.dataframe(top_over, use_container_width=True, hide_index=True, height=380)

    with cR:
        st.markdown(f"<div style='font-size:.85rem;color:{C['red']};margin-bottom:.5rem'>"
                    f"🚨 Top 10 Understocked — SS too thin</div>", unsafe_allow_html=True)
        top_under = under.nsmallest(10, 'delta_value')[
            ['material_code', 'description', 'ss_current', 'ss_optimal', 'delta_value', 'abc_class', 'xyz_class']
        ].copy()
        top_under['delta_value'] = top_under['delta_value'].apply(lambda v: fmt(abs(v)))
        top_under.columns = ['Code', 'Description', 'Current SS', 'Optimal SS', '₹ at Risk', 'ABC', 'XYZ']
        st.dataframe(top_under, use_container_width=True, hide_index=True, height=380)

    # ── ABC × delta breakdown ─────────────────────────────────────────────
    st.markdown("---")
    section_header("Releasable Capital by ABC Class")
    abc_break = (df.assign(bucket=np.where(df['delta_value'] >= 0, 'Releasable', 'Shortfall'))
                   .groupby(['abc_class', 'bucket'])['delta_value'].sum().reset_index())
    abc_break['delta_value'] = abc_break['delta_value'].abs()
    if not abc_break.empty:
        abc_pivot = abc_break.pivot(index='abc_class', columns='bucket', values='delta_value').fillna(0).reset_index()
        for col in ('Releasable', 'Shortfall'):
            if col not in abc_pivot.columns:
                abc_pivot[col] = 0
        fig = dark_group_bar(
            abc_pivot, 'abc_class',
            ['Releasable', 'Shortfall'],
            ['Releasable ₹', 'Shortfall ₹'],
            [C['green'], C['red']],
            height=280, title=None
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Material drill-down ───────────────────────────────────────────────
    st.markdown("---")
    section_header("Material Drill-Down", badge="3-yr trend + forecast band")

    pick_options = (df.sort_values('delta_value', key=abs, ascending=False)
                      .head(200)['material_code'] + " — " + df['description'].fillna('').str[:60]).tolist()
    pick = st.selectbox("Pick a material (top 200 by impact)", pick_options, key="fc_drill")
    if pick:
        mc = pick.split(" — ")[0]
        row = df[df['material_code'] == mc].iloc[0]

        years = ['FY 22-23', 'FY 23-24', 'FY 24-25', 'Forecast 25-26']
        actuals = [row['fy_2022_23'], row['fy_2023_24'], row['fy_2024_25'], row['forecast_next_year']]
        lower = [None, None, None, row['forecast_lower_band']]
        upper = [None, None, None, row['forecast_upper_band']]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=years[:3], y=actuals[:3], mode='lines+markers',
            name='Actual', line=dict(color=C['teal'], width=3),
            marker=dict(size=10, color=C['teal'])
        ))
        fig.add_trace(go.Scatter(
            x=years[2:], y=actuals[2:], mode='lines+markers',
            name='Forecast', line=dict(color=C['amber'], width=3, dash='dash'),
            marker=dict(size=10, color=C['amber'])
        ))
        if pd.notna(row['forecast_upper_band']) and pd.notna(row['forecast_lower_band']):
            fig.add_trace(go.Scatter(
                x=[years[3], years[3]],
                y=[row['forecast_lower_band'], row['forecast_upper_band']],
                mode='lines', line=dict(color=C['amber'], width=10),
                opacity=0.25, name='±2σ band', showlegend=True
            ))
        fig.update_layout(**plotly_base(height=320,
            title=dict(text=f"{mc} — Annual Consumption", font=dict(size=12, color=C["text"])),
            legend=dict(orientation='h', y=1.12)))
        st.plotly_chart(fig, use_container_width=True)

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Current SS", f"{row['ss_current']:.0f}")
        d2.metric(f"Optimal SS @ {sl}%", f"{row['ss_optimal']:.0f}")
        delta_lbl = "Releasable ₹" if row['delta_value'] >= 0 else "Shortfall ₹"
        d3.metric(delta_lbl, fmt(abs(row['delta_value'])))
        d4.metric("Lead Time (days)", f"{row['lead_time_days']:.0f}" if pd.notna(row['lead_time_days']) else "–")

        if row.get('xyz_class') == 'Z':
            alert_box("This is a <b>Z-class</b> (highly volatile) item. The optimal SS formula assumes normal demand and may understate the true buffer needed. Treat the recommendation as directional.", "warning")

    # ── Full table ────────────────────────────────────────────────────────
    st.markdown("---")
    section_header("All Analyzable Materials")
    show = df[['material_code', 'description', 'abc_class', 'xyz_class',
               'ss_current', 'ss_optimal', 'delta_qty', 'delta_value',
               'lead_time_days', 'avg_annual_consumption', 'consumption_volatility']].copy()
    show = show.sort_values('delta_value', ascending=False)
    show['delta_value'] = show['delta_value'].apply(fmt)
    show.columns = ['Code', 'Description', 'ABC', 'XYZ',
                    'Current SS', 'Optimal SS', 'Δ Qty', 'Δ ₹',
                    'LT (days)', 'Annual Cons.', 'CV']
    st.dataframe(show, use_container_width=True, hide_index=True, height=420)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — AI ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════
def _pr_drafts_to_excel_bytes(drafts):
    """Serialize accumulated PR drafts to an Excel byte stream for download."""
    df = pd.DataFrame(drafts)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='PR Drafts', index=False)
    return buf.getvalue()


def _render_tool_breadcrumbs(tool_calls):
    """Render compact tool-call breadcrumbs above an assistant message."""
    if not tool_calls:
        return
    pills = []
    for tc in tool_calls:
        name = tc.get('tool', '?')
        inp = tc.get('input', {})
        # Show the first key/value as a hint of what was looked up
        if inp:
            k = next(iter(inp))
            preview = str(inp[k])
            if len(preview) > 50:
                preview = preview[:47] + '…'
            label = f"{name}({k}={preview})"
        else:
            label = name
        is_err = isinstance(tc.get('output'), dict) and 'error' in tc['output']
        color = C['red'] if is_err else C['purple']
        pills.append(
            f"<span style='background:{color}15;color:{color};border:1px solid {color}40;"
            f"border-radius:6px;padding:.15rem .55rem;font-size:.7rem;font-family:{C['mono']};"
            f"margin-right:.4rem;display:inline-block'>🔧 {label}</span>"
        )
    st.markdown(
        f"<div style='margin:.3rem 0 .5rem 0'>{''.join(pills)}</div>",
        unsafe_allow_html=True,
    )


def page_ai():
    st.markdown(f"""
    <h1>AI Assistant</h1>
    <p style='color:{C["text"]};font-family:{C["mono"]};font-size:.78rem;margin-bottom:1.2rem'>
        Tool-calling Claude · Memory across turns · 5 tools (SQL, forecast, supplier risk, draft PR)
    </p>""", unsafe_allow_html=True)

    if not os.getenv('ANTHROPIC_API_KEY'):
        alert_box(
            "ANTHROPIC_API_KEY is not set. "
            "Go to Streamlit Cloud → your app → <b>Settings → Secrets</b> and add:<br>"
            "<code>ANTHROPIC_API_KEY = \"sk-ant-...\"</code>",
            "critical"
        )
        return

    EXAMPLES = [
        "Top 3 highest-risk suppliers and why",
        "Forecast next year for material 48060",
        "Critical P9 items — draft PRs for the top 3",
        "Compare P9 vs 21C compliance",
        "Single-source A-class exposure",
        "Releasable working capital at 98% SL",
    ]

    # ── Session state init ────────────────────────────────────────────────
    st.session_state.setdefault('ai_chat_history', [])   # API-format messages
    st.session_state.setdefault('ai_display', [])        # render-format turns
    st.session_state.setdefault('pr_drafts', [])
    st.session_state.setdefault('ai_chip_query', '')

    # Clear textarea before any widget is instantiated (Streamlit forbids
    # writing to a widget's session key after the widget has rendered).
    if st.session_state.pop('_clear_textarea', False):
        st.session_state['ai_textarea'] = ''

    # ── PR drafts panel (visible only if drafts exist) ────────────────────
    if st.session_state['pr_drafts']:
        section_header("Drafted Purchase Requisitions",
                       badge=f"{len(st.session_state['pr_drafts'])} queued")
        df_pr = pd.DataFrame(st.session_state['pr_drafts'])
        st.dataframe(df_pr, use_container_width=True, hide_index=True, height=200)
        c1, c2, _ = st.columns([2, 2, 6])
        with c1:
            st.download_button(
                "⬇️  Download as Excel",
                data=_pr_drafts_to_excel_bytes(st.session_state['pr_drafts']),
                file_name=f"pr_drafts_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with c2:
            if st.button("🗑️  Clear drafts", use_container_width=True, key="clear_pr"):
                st.session_state['pr_drafts'] = []
                st.rerun()
        st.markdown("---")

    # ── Quick-query chips ─────────────────────────────────────────────────
    section_header("Quick Queries")
    cols = st.columns(len(EXAMPLES))
    for i, ex in enumerate(EXAMPLES):
        with cols[i]:
            if st.button(ex, key=f"qex_{i}", use_container_width=True):
                st.session_state['ai_chip_query'] = ex
                st.session_state['ai_textarea'] = ex  # directly update widget state (Streamlit Cloud compat)
                st.rerun()

    st.markdown("---")

    # ── Conversation transcript ───────────────────────────────────────────
    section_header("Conversation")
    if not st.session_state['ai_display']:
        st.markdown(
            f"<div style='color:{C['text']};font-size:.85rem;padding:.6rem 0'>"
            f"No messages yet. Pick a quick query above or type a question below.</div>",
            unsafe_allow_html=True,
        )
    else:
        for turn in st.session_state['ai_display']:
            if turn['role'] == 'user':
                st.markdown(
                    f"<div style='background:{C['surface2']};border-radius:10px;padding:.7rem 1rem;"
                    f"margin:.5rem 0;font-size:.88rem;color:{C['text_bright']};border-left:3px solid {C['teal']}'>"
                    f"<b style='color:{C['teal']};font-size:.7rem;letter-spacing:.1em'>YOU</b><br>"
                    f"{turn['text']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                _render_tool_breadcrumbs(turn.get('tool_calls', []))
                body = turn['text'].replace('\n', '<br>').replace('**', '')
                st.markdown(
                    f"<div style='background:{C['surface']};border:1px solid {C['border']};"
                    f"border-left:3px solid {C['amber']};border-radius:10px;padding:1rem 1.2rem;"
                    f"margin:.4rem 0 1rem 0;font-size:.88rem;line-height:1.7;color:{C['text_bright']}'>"
                    f"<b style='color:{C['amber']};font-size:.7rem;letter-spacing:.1em'>ASSISTANT</b><br>"
                    f"{body}</div>",
                    unsafe_allow_html=True,
                )

    # ── Input area ────────────────────────────────────────────────────────
    section_header("Ask Anything")
    query = st.text_area(
        "",
        placeholder="e.g. For the highest-risk supplier, list their A-class items.",
        height=95, label_visibility="collapsed", key="ai_textarea",
    )

    c1, c2, _ = st.columns([2, 1, 7])
    with c1:
        go_btn = st.button("⚡  Analyze", type="primary", use_container_width=True)
    with c2:
        if st.button("↺  Reset Chat", use_container_width=True):
            st.session_state['ai_chat_history'] = []
            st.session_state['ai_display'] = []
            st.session_state['ai_chip_query'] = ''
            st.session_state['_clear_textarea'] = True  # cleared at top of next run
            st.rerun()

    if go_btn:
        final_query = query.strip()
        if not final_query:
            alert_box("Type a question or pick a quick query.", "warning")
        else:
            st.session_state['ai_chip_query'] = ''  # consume the chip
            with st.spinner("Thinking & looking things up…"):
                try:
                    result = agent_chat(final_query, history=st.session_state['ai_chat_history'])
                except Exception as e:
                    alert_box(f"Agent error: {e}", "critical")
                    return

            # Append display turns
            st.session_state['ai_display'].append({'role': 'user', 'text': final_query})
            st.session_state['ai_display'].append({
                'role': 'assistant',
                'text': result['reply'],
                'tool_calls': result['tool_calls'],
            })

            # Round-trip the API history (trim oldest turns to bound context)
            new_history = result['history']
            # Each "turn" is up to 3 messages (user, assistant, tool_result), so
            # cap by message count rather than turn count.
            if len(new_history) > HISTORY_TURN_CAP * 3:
                new_history = new_history[-HISTORY_TURN_CAP * 3:]
            st.session_state['ai_chat_history'] = new_history

            # Capture any draft_pr outputs into the PR-drafts queue
            for tc in result['tool_calls']:
                out = tc.get('output')
                if tc.get('tool') == 'draft_pr' and isinstance(out, dict) and 'error' not in out:
                    st.session_state['pr_drafts'].append(out)

            st.rerun()

    with st.expander("📖  Example Questions"):
        st.markdown("""
**📊 Lookups (uses query_db)**
- Top 20 materials by stock value
- Materials below safety stock in P9
- TBO breakdown by supplier

**🔮 Forecasting (uses forecast_material)**
- Forecast demand for 48060 next year
- Optimal safety stock for material 70809 at 99% service level
- For my top 5 A-class items, compare current vs optimal SS

**🛡️ Supplier risk (uses supplier_risk)**
- Risk profile of SONEPAR INDIA PVT LTD
- Suppliers with single-source A-class exposure
- Spend concentration of top 5 suppliers

**📝 Action (uses draft_pr)**
- Draft a PR for material 48060, qty 100
- Critical P9 items — draft PRs for the top 3 by shortage
        """)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    if not os.path.exists(DB_PATH):
        st.markdown("<h1>⚡ Procurement Command Center</h1>", unsafe_allow_html=True)
        alert_box(f"Database <b>{DB_PATH}</b> not found.", "critical")
        st.code("python prepare_data_final.py", language="bash")
        return

    page = sidebar()

    if "Overview"     in page: page_overview()
    elif "Optimiz"    in page: page_optimization()
    elif "Inventory"  in page: page_inventory()
    elif "Forecast"   in page: page_forecast()
    elif "AI"         in page: page_ai()

if __name__ == "__main__":
    main()
