"""
FINAL Data Preparation Script (v3.0)
=====================================
This is the ONLY data prep script you need.
Integrates ALL data sources into one database:
  1. Stock Status (all 4 plants: 419 AT, 419 PD, 21C, P9)
  2. Historical Consumption + Lead Times (21C MRP items)
  3. P9 Planning Sheets (suppliers, TBO, pending orders)
  4. 21C Safety Stock Sheet (suppliers, TBO, pending orders)

Output: procurement_final.db

Usage:
  python prepare_data_final.py
"""

import pandas as pd
import sqlite3
import numpy as np
import math
from datetime import datetime
import warnings
import os
from forecasting import add_forecast_columns
from supplier_analytics import compute_supplier_risk
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION - Update these paths if your files are in different locations
# ============================================================================

DATA_DIR = 'Data'

FILES = {
    'stock_status':    os.path.join(DATA_DIR, 'STOCK STATUS DT 31.03.2026.xlsx'),
    'historical':      os.path.join(DATA_DIR, 'Lead Time _21c 3yr MRP items consumption.xlsx'),
    'p9_planning_1':   os.path.join(DATA_DIR, 'P9 COMBINED PLANNING SHEET - 13.04.26, MP- 106 & FFB BRAZIL- 65.xlsx'),
    'p9_planning_2':   os.path.join(DATA_DIR, 'P9 COMBINED PLANNING SHEET - 14.04-2026 FFB - 285 Nos.xlsx'),
    '21c_safety':      os.path.join(DATA_DIR, 'SAFETY STOCK 21C UPDATED WORKING.xlsx'),
}

DB_PATH = 'procurement_final.db'

# ============================================================================
# STEP 1: LOAD STOCK STATUS (All 4 Plants)
# ============================================================================

def load_stock_status():
    """Load stock status across all 4 plants"""
    
    print("\n[1/5] Loading Stock Status (all plants)...")
    
    path = FILES['stock_status']
    if not os.path.exists(path):
        print(f"  ⚠️ File not found: {path} - skipping")
        return pd.DataFrame()
    
    df = pd.read_excel(path, sheet_name='Sheet1')
    
    # Parse multi-level headers
    plant_row = df.iloc[0]
    col_row = df.iloc[1]
    df_data = df.iloc[2:].reset_index(drop=True)
    
    # Build column names
    new_cols = []
    current_plant = None
    for i, (plant, col) in enumerate(zip(plant_row, col_row)):
        if pd.notna(plant) and plant not in ['Sr No', 'Part No', 'Description', 'UOM']:
            current_plant = str(plant).strip()
        if col in ['Sr No', 'Part No', 'Description', 'UOM', 'Total Qty', 'Total Amount']:
            new_cols.append(str(col))
        elif col in ['Qty', 'Mauc Rate', 'Amount']:
            new_cols.append(f"{current_plant}_{col}" if current_plant else str(col))
        else:
            new_cols.append(str(col) if pd.notna(col) else f"Col_{i}")
    
    df_data.columns = new_cols
    
    # Build material master
    mm = df_data[['Part No', 'Description', 'UOM']].copy()
    mm.columns = ['material_code', 'description', 'uom']
    
    plants = ['419 AT', '419 PD', '21C', 'P9']
    for plant in plants:
        key = plant.lower().replace(' ', '_')
        for suffix, label in [('Qty', 'stock'), ('Mauc Rate', 'muac_rate'), ('Amount', 'stock_value')]:
            col = f"{plant}_{suffix}"
            if col in df_data.columns:
                mm[f'{label}_{key}'] = pd.to_numeric(df_data[col], errors='coerce').fillna(0)
    
    mm['total_stock_qty'] = pd.to_numeric(df_data.get('Total Qty', 0), errors='coerce').fillna(0)
    mm['total_stock_value'] = pd.to_numeric(df_data.get('Total Amount', 0), errors='coerce').fillna(0)
    mm['avg_muac_rate'] = np.where(mm['total_stock_qty'] > 0, mm['total_stock_value'] / mm['total_stock_qty'], 0)
    
    print(f"  ✓ {len(mm)} materials loaded from stock status")
    return mm

# ============================================================================
# STEP 2: LOAD HISTORICAL CONSUMPTION + LEAD TIMES (21C)
# ============================================================================

def load_historical_data():
    """Load 3-year consumption history and lead times"""
    
    print("\n[2/5] Loading Historical Consumption & Lead Times...")
    
    path = FILES['historical']
    if not os.path.exists(path):
        print(f"  ⚠️ File not found: {path} - skipping")
        return pd.DataFrame()
    
    df = pd.read_excel(path, sheet_name='Sheet2', header=None)
    df = df.iloc[1:].copy()
    df.columns = ['sr_no', 'material_code', 'description', 'fy_2022_23',
                   'fy_2023_24', 'fy_2024_25', 'total_3yr', 'safety_stock_hist', 'lead_time_days']
    
    for col in ['fy_2022_23', 'fy_2023_24', 'fy_2024_25', 'total_3yr', 'safety_stock_hist', 'lead_time_days']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df[['material_code', 'fy_2022_23', 'fy_2023_24', 'fy_2024_25',
             'total_3yr', 'safety_stock_hist', 'lead_time_days']].copy()
    
    print(f"  ✓ {len(df)} materials with historical data")
    return df

# ============================================================================
# STEP 3: LOAD P9 PLANNING SHEETS
# ============================================================================

def load_p9_planning():
    """Load P9 planning sheets (suppliers, TBO, pending orders)"""
    
    print("\n[3/5] Loading P9 Planning Sheets...")
    
    path = FILES['p9_planning_2']  # Use newer file (14-Apr) as primary
    if not os.path.exists(path):
        print(f"  ⚠️ File not found: {path} - skipping")
        return pd.DataFrame()
    
    df = pd.read_excel(path, sheet_name='P9 PLANNING SHEET', header=1)
    
    df = df.rename(columns={
        'Item Code': 'material_code',
        'Description': 'description',
        'UOM': 'uom',
        'Total Req': 'total_requirement',
        'Stock of P9 as on': 'current_stock',
        'Allocation P9 as on': 'allocation',
        'Shortage (-) / Surplus(+) at the moment': 'current_shortage_surplus',
        'Pending Order as on': 'pending_order_qty',
        'Net Surplus (+) / Deficiency (-)': 'net_position',
        'Safety Stock P9': 'safety_stock',
        'Shortage (-) / Surplus (+) considering Safety stock': 'safety_stock_gap',
        'TBO': 'tbo_qty',
        'Lead Time (Weeks)': 'lead_time_weeks',
        'Unit Price': 'unit_price',
        'Order Amount (INR)': 'order_amount',
        'Remarks/ SUPPLIER': 'supplier_name',
        'Stock Value': 'stock_value',
        'Allocation Value': 'allocation_value',
        'Pending Order Value': 'pending_order_value',
        'PO No.': 'po_number',
        'Remarks': 'remarks'
    })
    
    # Fallback column name
    if 'Remarks/Supplier' in df.columns:
        df = df.rename(columns={'Remarks/Supplier': 'supplier_name'})
    
    df['warehouse'] = 'P9'
    df['data_date'] = '2026-04-14'
    df['annual_consumption'] = np.nan
    
    # Ensure numeric
    for col in ['current_stock', 'allocation', 'pending_order_qty', 'safety_stock',
                'safety_stock_gap', 'tbo_qty', 'unit_price', 'order_amount',
                'stock_value', 'allocation_value', 'pending_order_value', 'lead_time_weeks']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    print(f"  ✓ P9: {len(df)} materials loaded")
    return df

# ============================================================================
# STEP 4: LOAD 21C SAFETY STOCK SHEET
# ============================================================================

def load_21c_safety_stock():
    """Load 21C safety stock / planning sheet"""
    
    print("\n[4/5] Loading 21C Safety Stock Sheet...")
    
    path = FILES['21c_safety']
    if not os.path.exists(path):
        print(f"  ⚠️ File not found: {path} - skipping")
        return pd.DataFrame()
    
    df = pd.read_excel(path, sheet_name='Sheet1', header=3)
    
    df = df.rename(columns={
        'Part no.': 'material_code',
        'Description': 'description',
        'Current Safety Stock 21C': 'current_safety_stock',
        'Annual Consumption 2025-26 -21C': 'annual_consumption',
        '1.5 Month Req': 'monthly_req_1_5',
        'Diff w.r.t current Safety Stock': 'safety_stock_diff',
        'Safety Stock Considered for Topping Up': 'safety_stock',
        'Stock 21C': 'current_stock',
        'Allocation 21C': 'allocation',
        'Pending Orders 21C': 'pending_order_qty',
        'Net Shortage / Surplus': 'safety_stock_gap',
        'TBO': 'tbo_qty',
        'Unit Rate': 'unit_price',
        'Order Amt': 'order_amount',
        'Vendor': 'supplier_name',
        'Remarks': 'remarks'
    })
    
    df['warehouse'] = '21C'
    df['data_date'] = '2026-04-17'
    df['lead_time_weeks'] = np.nan
    
    # Ensure numeric
    for col in ['current_stock', 'allocation', 'pending_order_qty', 'safety_stock',
                'safety_stock_gap', 'tbo_qty', 'unit_price', 'order_amount',
                'annual_consumption']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Derived values
    df['stock_value'] = df['current_stock'].fillna(0) * df['unit_price'].fillna(0)
    df['allocation_value'] = df['allocation'].fillna(0) * df['unit_price'].fillna(0)
    df['pending_order_value'] = df['pending_order_qty'].fillna(0) * df['unit_price'].fillna(0)
    
    print(f"  ✓ 21C: {len(df)} materials loaded")
    return df

# ============================================================================
# STEP 5: COMBINE, CALCULATE, AND SAVE
# ============================================================================

def combine_planning_data(df_p9, df_21c):
    """Combine P9 and 21C planning data into unified format"""
    
    common_cols = [
        'material_code', 'description', 'warehouse', 'data_date',
        'current_stock', 'allocation', 'pending_order_qty',
        'safety_stock', 'safety_stock_gap', 'tbo_qty',
        'unit_price', 'order_amount', 'supplier_name',
        'stock_value', 'allocation_value', 'pending_order_value',
        'lead_time_weeks', 'annual_consumption', 'remarks'
    ]
    
    frames = []
    for df in [df_p9, df_21c]:
        if len(df) > 0:
            # Add missing columns
            for col in common_cols:
                if col not in df.columns:
                    df[col] = np.nan
            frames.append(df[common_cols].copy())
    
    if frames:
        combined = pd.concat(frames, ignore_index=True)
    else:
        combined = pd.DataFrame(columns=common_cols)
    
    return combined

def calculate_enhanced_tbo(row):
    """
    Enhanced TBO calculation using Reorder Point method
    
    Formula:
      Available = Current Stock + Pending Orders - Allocations
      ROP = (Lead Time × Daily Demand) + Safety Stock
      TBO = max(0, ROP - Available)
    """
    stock = float(row.get('current_stock', 0) or 0)
    pending = float(row.get('pending_order_qty', 0) or 0)
    alloc = float(row.get('allocation', 0) or 0)
    ss = float(row.get('safety_stock', 0) or 0)
    annual = float(row.get('annual_consumption', 0) or 0)
    lt_weeks = float(row.get('lead_time_weeks', 0) or 0)
    
    # Handle any remaining NaN
    stock = 0 if pd.isna(stock) else stock
    pending = 0 if pd.isna(pending) else pending
    alloc = 0 if pd.isna(alloc) else alloc
    ss = 0 if pd.isna(ss) else ss
    annual = 0 if pd.isna(annual) else annual
    lt_weeks = 0 if pd.isna(lt_weeks) else lt_weeks
    
    available = stock + pending - alloc
    
    if annual > 0 and lt_weeks > 0:
        daily = annual / 365
        rop = (lt_weeks * 7 * daily) + ss
    else:
        rop = ss
    
    shortage = rop - available
    
    if pd.isna(shortage) or shortage <= 0:
        return 0, 'None', available, rop
    
    # Round up to nearest 10
    tbo = math.ceil(float(shortage) / 10) * 10
    
    # Priority
    if pd.isna(ss) or ss == 0:
        priority = 'Medium'
    elif shortage > ss:
        priority = 'High'
    elif shortage > ss * 0.5:
        priority = 'Medium'
    else:
        priority = 'Low'
    
    return tbo, priority, available, rop

def build_supplier_master(df):
    """Build supplier master from combined data"""
    
    suppliers = df[df['supplier_name'].notna()]['supplier_name'].unique()
    rows = []
    for s in suppliers:
        sub = df[df['supplier_name'] == s]
        rows.append({
            'supplier_name': s,
            'material_count': len(sub),
            'warehouse_count': sub['warehouse'].nunique(),
            'warehouses': ', '.join(sorted(sub['warehouse'].dropna().unique())),
            'total_order_value': sub['order_amount'].sum(),
            'avg_lead_time_weeks': sub['lead_time_weeks'].mean(),
        })
    return pd.DataFrame(rows).sort_values('material_count', ascending=False)

def build_database(df_stock, df_hist, df_planning):
    """Build the final SQLite database"""
    
    print("\n[5/5] Building Final Database...")
    
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    
    # ---- Table 1: stock_master (from stock status file) ----
    if len(df_stock) > 0:
        # Merge historical data
        if len(df_hist) > 0:
            df_stock = df_stock.merge(df_hist, on='material_code', how='left')
        
        # Calculate metrics
        df_stock['avg_annual_consumption'] = df_stock[['fy_2022_23', 'fy_2023_24', 'fy_2024_25']].mean(axis=1) if 'fy_2022_23' in df_stock.columns else 0
        df_stock['avg_daily_consumption'] = df_stock['avg_annual_consumption'] / 365 if 'avg_annual_consumption' in df_stock.columns else 0
        
        if 'avg_annual_consumption' in df_stock.columns:
            std = df_stock[['fy_2022_23', 'fy_2023_24', 'fy_2024_25']].std(axis=1)
            df_stock['consumption_volatility'] = (std / df_stock['avg_annual_consumption']).fillna(0)
        
        # Days of inventory
        if 'avg_daily_consumption' in df_stock.columns:
            df_stock['days_of_inventory'] = (df_stock['total_stock_qty'] / df_stock['avg_daily_consumption']).replace([np.inf, -np.inf], 0).fillna(0)
            df_stock['inventory_turnover_ratio'] = np.where(df_stock['total_stock_qty'] > 0, df_stock['avg_annual_consumption'] / df_stock['total_stock_qty'], 0)
        
        # Reorder point
        if 'lead_time_days' in df_stock.columns:
            df_stock['reorder_point'] = (df_stock['lead_time_days'] * df_stock['avg_daily_consumption'] + df_stock.get('safety_stock_hist', 0)).fillna(0)
            df_stock['stock_vs_rop'] = df_stock['total_stock_qty'] - df_stock['reorder_point']
            df_stock['stock_status'] = np.where(df_stock['stock_vs_rop'] < 0, 'Below ROP', np.where(df_stock['stock_vs_rop'] < df_stock.get('safety_stock_hist', 0), 'Near ROP', 'Above ROP'))
        
        # Excess stock
        if 'reorder_point' in df_stock.columns:
            optimal = df_stock['reorder_point'] + df_stock.get('safety_stock_hist', 0)
            df_stock['excess_stock_qty'] = np.where(df_stock['total_stock_qty'] > optimal, df_stock['total_stock_qty'] - optimal, 0)
            df_stock['excess_stock_value'] = df_stock['excess_stock_qty'] * df_stock['avg_muac_rate']
        
        # ABC classification
        df_stock = df_stock.sort_values('total_stock_value', ascending=False)
        df_stock['cum_pct'] = df_stock['total_stock_value'].cumsum() / df_stock['total_stock_value'].sum() * 100
        df_stock['abc_class'] = df_stock['cum_pct'].apply(lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C'))
        
        # XYZ classification
        if 'consumption_volatility' in df_stock.columns:
            df_stock['xyz_class'] = df_stock['consumption_volatility'].apply(lambda x: 'X' if x < 0.25 else ('Y' if x < 0.5 else 'Z'))

        # Demand forecast + optimal safety stock at 95/98/99% service levels
        df_stock = add_forecast_columns(df_stock)

        df_stock.to_sql('stock_master', conn, if_exists='replace', index=False)
        print(f"  ✓ stock_master: {len(df_stock)} rows (all 4 plants inventory)")
    
    # ---- Table 2: planning_master (P9 + 21C planning) ----
    if len(df_planning) > 0:
        # Calculate enhanced TBO
        tbo_results = df_planning.apply(calculate_enhanced_tbo, axis=1, result_type='expand')
        df_planning['tbo_enhanced'] = tbo_results[0]
        df_planning['tbo_priority'] = tbo_results[1]
        df_planning['available_inventory'] = tbo_results[2]
        df_planning['reorder_point'] = tbo_results[3]
        
        # Criticality flag
        df_planning['is_critical'] = (
            (df_planning['safety_stock_gap'] < 0) & 
            ((df_planning['tbo_qty'].isna()) | (df_planning['tbo_qty'] == 0))
        ).astype(int)
        
        df_planning.to_sql('planning_master', conn, if_exists='replace', index=False)
        print(f"  ✓ planning_master: {len(df_planning)} rows (P9 + 21C planning)")
    
    # ---- Table 3: supplier_master ----
    if len(df_planning) > 0:
        df_suppliers = build_supplier_master(df_planning)
        df_suppliers.to_sql('supplier_master', conn, if_exists='replace', index=False)
        print(f"  ✓ supplier_master: {len(df_suppliers)} suppliers")

    # ---- Table 3b: supplier_risk (concentration & single-source scoring) ----
    if len(df_planning) > 0:
        df_risk = compute_supplier_risk(conn)
        if len(df_risk) > 0:
            df_risk.to_sql('supplier_risk', conn, if_exists='replace', index=False)
            print(f"  ✓ supplier_risk: {len(df_risk)} suppliers scored "
                  f"({(df_risk['risk_tier']=='Critical').sum()} Critical, "
                  f"{(df_risk['risk_tier']=='High').sum()} High)")
    
    # ---- Table 4: tbo_orders (materials needing orders) ----
    if len(df_planning) > 0:
        df_tbo = df_planning[df_planning['tbo_qty'].notna() & (df_planning['tbo_qty'] > 0)].copy()
        df_tbo.to_sql('tbo_orders', conn, if_exists='replace', index=False)
        print(f"  ✓ tbo_orders: {len(df_tbo)} materials to order")
    
    # ---- Table 5: pending_orders ----
    if len(df_planning) > 0:
        df_pending = df_planning[df_planning['pending_order_qty'].notna() & (df_planning['pending_order_qty'] > 0)].copy()
        df_pending.to_sql('pending_orders', conn, if_exists='replace', index=False)
        print(f"  ✓ pending_orders: {len(df_pending)} orders in pipeline")
    
    # ---- Table 6: stock_by_location (from stock status) ----
    if len(df_stock) > 0:
        loc_rows = []
        for _, row in df_stock.iterrows():
            for plant in ['419_at', '419_pd', '21c', 'p9']:
                scol = f'stock_{plant}'
                if scol in df_stock.columns and row[scol] > 0:
                    loc_rows.append({
                        'material_code': row['material_code'],
                        'plant_code': plant.upper().replace('_', ' '),
                        'stock_qty': row[scol],
                        'muac_rate': row.get(f'muac_rate_{plant}', 0),
                        'stock_value': row.get(f'stock_value_{plant}', 0),
                    })
        if loc_rows:
            pd.DataFrame(loc_rows).to_sql('stock_by_location', conn, if_exists='replace', index=False)
            print(f"  ✓ stock_by_location: {len(loc_rows)} records")
    
    # ---- Views ----
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_warehouse_summary AS
        SELECT warehouse,
               COUNT(*) as material_count,
               ROUND(SUM(stock_value), 2) as total_stock_value,
               ROUND(SUM(order_amount), 2) as total_tbo_value,
               ROUND(SUM(pending_order_value), 2) as total_pending_value,
               SUM(CASE WHEN safety_stock_gap < 0 THEN 1 ELSE 0 END) as below_safety,
               SUM(is_critical) as critical_count
        FROM planning_master GROUP BY warehouse
    """)
    
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_critical_materials AS
        SELECT warehouse, material_code, description,
               current_stock, safety_stock, safety_stock_gap,
               tbo_qty, supplier_name
        FROM planning_master
        WHERE is_critical = 1
        ORDER BY warehouse, safety_stock_gap ASC
    """)
    
    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_wh ON planning_master(warehouse)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_mat ON planning_master(material_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_sup ON planning_master(supplier_name)")
    
    # Only create stock index if table exists
    tables_created = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if 'stock_master' in tables_created:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_mat ON stock_master(material_code)")
    
    conn.commit()
    
    # ---- Print Summary ----
    print("\n" + "="*80)
    print("FINAL DATABASE SUMMARY")
    print("="*80)
    
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"\nTables: {[t[0] for t in tables]}")
    
    if len(df_planning) > 0:
        for wh in df_planning['warehouse'].unique():
            sub = df_planning[df_planning['warehouse'] == wh]
            crit = sub['is_critical'].sum()
            tbo_val = sub['order_amount'].sum()
            pend_val = sub['pending_order_value'].sum()
            below = (sub['safety_stock_gap'] < 0).sum()
            print(f"\n{wh} Warehouse:")
            print(f"  Materials: {len(sub):,}")
            print(f"  Below Safety Stock: {below:,}")
            print(f"  Critical (no TBO): {crit:,}")
            print(f"  TBO Value: ₹{tbo_val:,.2f}")
            print(f"  Pending Orders: ₹{pend_val:,.2f}")
    
    if len(df_stock) > 0:
        total_inv = df_stock['total_stock_value'].sum()
        print(f"\nStock Status (All Plants):")
        print(f"  Materials: {len(df_stock):,}")
        print(f"  Total Inventory: ₹{total_inv:,.2f}")
    
    conn.close()
    print(f"\n✅ Database created: {DB_PATH}")

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*80)
    print("PROCUREMENT ANALYTICS - FINAL DATA BUILDER")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check which files exist
    print("\nChecking data files...")
    for key, path in FILES.items():
        status = "✅" if os.path.exists(path) else "❌ NOT FOUND"
        print(f"  {status} {key}: {path}")
    
    # Load each data source
    df_stock = load_stock_status()
    df_hist = load_historical_data()
    df_p9 = load_p9_planning()
    df_21c = load_21c_safety_stock()
    
    # Combine planning data
    df_planning = combine_planning_data(df_p9, df_21c)
    print(f"\n  Combined planning: {len(df_planning)} materials across {df_planning['warehouse'].nunique()} warehouses")
    
    # Build database
    build_database(df_stock, df_hist, df_planning)
    
    print("\n" + "="*80)
    print("✨ DONE! Run your app with:")
    print("   streamlit run app.py")
    print("="*80)

if __name__ == "__main__":
    main()
