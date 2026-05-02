"""
Forecasting & Service-Level-Driven Safety Stock
================================================
Adds two analytics columns to stock_master:
  - Demand forecast for next year (recency-weighted moving average)
  - Optimal safety stock at 95/98/99% service levels

Intentionally simple. With only 3 yearly data points per material, an ARIMA or
Prophet model would over-fit; a recency-weighted blend is more honest and
defensible to the procurement team.

Formulas
--------
Forecast:
    forecast = 0.5 * fy_2024_25 + 0.3 * fy_2023_24 + 0.2 * fy_2022_23
    (weights re-normalised when a year is missing)

Optimal Safety Stock (continuous-review, normal demand):
    SS* = z(sl) * σ_annual * sqrt(LT_days / 365)

    where σ_annual = avg_annual_consumption * consumption_volatility
    (consumption_volatility is the coefficient of variation across 3 FYs).

Caveats
-------
- σ from 3 yearly observations is a noisy estimator. Treat the optimisation as
  directional, not predictive — flag XYZ='Z' (highly volatile) items so the
  user knows the recommendation is least reliable for them.
- Assumes demand is approximately normal. For lumpy / intermittent demand the
  formula understates SS.
"""

import numpy as np
import pandas as pd

# Service-level z-scores (one-sided normal distribution)
Z_SCORES = {
    95: 1.645,
    98: 2.054,
    99: 2.326,
}

# Forecast weights, most-recent year first
_FORECAST_WEIGHTS = np.array([0.5, 0.3, 0.2])  # fy_2024_25, fy_2023_24, fy_2022_23


def _recency_weighted_forecast(fy3, fy2, fy1):
    """
    Vectorised recency-weighted forecast.
    Re-normalises weights to drop missing years.

    Args:
        fy3, fy2, fy1: pandas Series of FY 2024-25, 2023-24, 2022-23 consumption.

    Returns:
        np.ndarray of forecasts, NaN where all three years are missing.
    """
    stack = np.vstack([
        pd.to_numeric(fy3, errors='coerce').values,
        pd.to_numeric(fy2, errors='coerce').values,
        pd.to_numeric(fy1, errors='coerce').values,
    ])
    mask = ~np.isnan(stack)

    weights = np.tile(_FORECAST_WEIGHTS[:, None], (1, stack.shape[1]))
    weights = np.where(mask, weights, 0.0)

    weight_sum = weights.sum(axis=0)
    weighted = np.where(mask, stack * weights, 0.0).sum(axis=0)

    return np.where(weight_sum > 0, weighted / np.where(weight_sum > 0, weight_sum, 1), np.nan)


def add_forecast_columns(df):
    """
    Add forecast and optimal-SS columns to a stock_master DataFrame.

    Required input columns:
        fy_2022_23, fy_2023_24, fy_2024_25,
        avg_annual_consumption, consumption_volatility,
        lead_time_days, avg_muac_rate, safety_stock_hist

    Adds:
        forecast_next_year, forecast_lower_band, forecast_upper_band,
        safety_stock_optimal_95, safety_stock_optimal_98, safety_stock_optimal_99,
        ss_delta_value_95, ss_delta_value_98, ss_delta_value_99
        (delta_value > 0 → working capital releasable;
         delta_value < 0 → SS too thin, stockout risk in ₹.)
    """
    df = df.copy()

    fy3 = df.get('fy_2024_25')
    fy2 = df.get('fy_2023_24')
    fy1 = df.get('fy_2022_23')

    if fy3 is None or fy2 is None or fy1 is None:
        # No historical consumption available — nothing to forecast.
        for col in ('forecast_next_year', 'forecast_lower_band', 'forecast_upper_band'):
            df[col] = np.nan
        for sl in Z_SCORES:
            df[f'safety_stock_optimal_{sl}'] = np.nan
            df[f'ss_delta_value_{sl}'] = np.nan
        return df

    forecast = _recency_weighted_forecast(fy3, fy2, fy1)

    avg_annual = pd.to_numeric(df.get('avg_annual_consumption', 0), errors='coerce').fillna(0).values
    cv = pd.to_numeric(df.get('consumption_volatility', 0), errors='coerce').fillna(0).values
    sigma_annual = avg_annual * cv

    df['forecast_next_year'] = forecast
    df['forecast_lower_band'] = np.maximum(0.0, forecast - 2.0 * sigma_annual)
    df['forecast_upper_band'] = forecast + 2.0 * sigma_annual

    lt_days = pd.to_numeric(df.get('lead_time_days', 0), errors='coerce').fillna(0).values
    sqrt_lt_years = np.sqrt(np.maximum(lt_days, 0.0) / 365.0)

    ss_hist = pd.to_numeric(df.get('safety_stock_hist'), errors='coerce').values
    muac = pd.to_numeric(df.get('avg_muac_rate', 0), errors='coerce').fillna(0).values

    has_signal = (sigma_annual > 0) & (lt_days > 0)

    for sl, z in Z_SCORES.items():
        ss_opt_raw = z * sigma_annual * sqrt_lt_years
        ss_opt = np.where(has_signal, ss_opt_raw, np.nan)
        df[f'safety_stock_optimal_{sl}'] = ss_opt

        # Delta vs historical SS (+ve = releasable working capital, -ve = shortfall)
        delta_qty = ss_hist - ss_opt
        df[f'ss_delta_value_{sl}'] = delta_qty * muac

    return df
