"""
Supplier Risk & Concentration Scoring
=====================================
Computes a per-supplier risk scorecard from planning_master + stock_master.

Risk components (weights chosen for procurement context, not arbitrary):
  40%  single_source_a_count  — sole supplier of ABC=A materials (single point of failure)
  30%  spend_pct              — share of total open spend (concentration)
  20%  lt_std_weeks           — lead-time inconsistency across the supplier's items
  10%  coverage_norm          — fewer warehouses served = harder to absorb a hit

Each factor is normalised to its max in the population (0–100) before weighting,
so the score is relative to the current supplier portfolio. Re-baselined each
time the database is rebuilt.

Output table: supplier_risk
"""

import pandas as pd
import numpy as np


_RISK_WEIGHTS = {
    'ss_a_norm':     0.40,
    'spend_norm':    0.30,
    'lt_norm':       0.20,
    'coverage_norm': 0.10,
}

_TIER_BINS = [-1, 25, 50, 75, 101]
_TIER_LABELS = ['Low', 'Medium', 'High', 'Critical']


def compute_supplier_risk(conn, total_warehouses=2):
    """
    Build a supplier-level risk DataFrame.

    Args:
        conn: sqlite3 connection with planning_master and stock_master tables.
        total_warehouses: denominator for coverage scoring (default 2: P9 + 21C).

    Returns:
        DataFrame sorted by risk_score DESC. Empty if no suppliers found.
    """
    df = pd.read_sql_query("""
        SELECT pm.supplier_name, pm.material_code, pm.warehouse,
               pm.order_amount, pm.pending_order_value, pm.lead_time_weeks,
               sm.abc_class
        FROM planning_master pm
        LEFT JOIN stock_master sm USING(material_code)
        WHERE pm.supplier_name IS NOT NULL
          AND TRIM(pm.supplier_name) != ''
    """, conn)

    if df.empty:
        return pd.DataFrame()

    df['open_value'] = df['order_amount'].fillna(0) + df['pending_order_value'].fillna(0)
    total_open = df['open_value'].sum()

    # Single-source detection: a material has only one distinct supplier in planning_master
    sup_per_mat = df.groupby('material_code')['supplier_name'].nunique()
    single_source_mats = set(sup_per_mat[sup_per_mat == 1].index)

    rows = []
    for sup, group in df.groupby('supplier_name'):
        materials = group[['material_code', 'abc_class']].drop_duplicates('material_code')

        ss_a_count = int(
            materials[materials['material_code'].isin(single_source_mats) &
                      (materials['abc_class'] == 'A')].shape[0]
        )
        ss_total = int(materials[materials['material_code'].isin(single_source_mats)].shape[0])

        sup_value = float(group['open_value'].sum())
        spend_pct = (sup_value / total_open * 100.0) if total_open > 0 else 0.0

        wh_count = int(group['warehouse'].nunique())

        lt_series = group['lead_time_weeks'].dropna()
        lt_std = float(lt_series.std()) if len(lt_series) >= 2 else 0.0
        lt_mean = float(lt_series.mean()) if len(lt_series) >= 1 else None

        rows.append({
            'supplier_name': sup,
            'material_count': int(materials.shape[0]),
            'warehouse_count': wh_count,
            'spend_value': round(sup_value, 2),
            'spend_pct': round(spend_pct, 2),
            'single_source_count': ss_total,
            'single_source_a_count': ss_a_count,
            'lt_mean_weeks': round(lt_mean, 2) if lt_mean is not None else None,
            'lt_std_weeks': round(lt_std, 2),
        })

    out = pd.DataFrame(rows)

    # Normalise each factor to 0–100 against population max
    def _norm(col):
        m = out[col].max()
        return (out[col] / m * 100.0) if m and m > 0 else out[col] * 0.0

    out['ss_a_norm'] = _norm('single_source_a_count')
    out['spend_norm'] = _norm('spend_pct')
    out['lt_norm'] = _norm('lt_std_weeks')
    out['coverage_norm'] = (1.0 - out['warehouse_count'] / max(total_warehouses, 1)) * 100.0

    out['risk_score'] = sum(out[c] * w for c, w in _RISK_WEIGHTS.items()).round(1)
    out['risk_tier'] = pd.cut(out['risk_score'], bins=_TIER_BINS, labels=_TIER_LABELS).astype(str)

    return out.sort_values('risk_score', ascending=False).reset_index(drop=True)
