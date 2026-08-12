from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from scipy.stats import poisson


def add_control_methods(predictions: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    df = predictions.sort_values(["geography_id", "period_start"]).copy()
    alpha = float(config["models"]["alert_alpha"])
    df["poisson_upper_ai"] = poisson.ppf(1 - alpha, np.maximum(df["expected_positive_ai"].fillna(0), 1e-9))
    df["poisson_upper_operational"] = poisson.ppf(1 - alpha, np.maximum(df["expected_positive_model"].fillna(0), 1e-9))
    g = df.groupby("geography_id", group_keys=False)
    prior = g["rr_mdr_positive"].shift(1)
    seasonal = g["rr_mdr_positive"].shift(4)
    rolling = g["rr_mdr_positive"].transform(lambda s: s.shift(1).rolling(4, min_periods=2).mean())
    rolling_sd = g["rr_mdr_positive"].transform(lambda s: s.shift(1).rolling(4, min_periods=2).std())
    ewma_mean = g["rr_mdr_positive"].transform(lambda s: s.shift(1).ewm(alpha=0.35, adjust=False, min_periods=1).mean())
    ewma_sd = g["rr_mdr_positive"].transform(lambda s: s.shift(1).ewm(alpha=0.35, adjust=False, min_periods=2).std())
    df["flag_persistence"] = df["rr_mdr_positive"] > poisson.ppf(1 - alpha, np.maximum(prior, 1e-9))
    df["flag_seasonal_naive"] = df["rr_mdr_positive"] > poisson.ppf(1 - alpha, np.maximum(seasonal, 1e-9))
    df["flag_shewhart"] = df["rr_mdr_positive"] > (rolling + 3 * rolling_sd.fillna(np.sqrt(rolling.clip(lower=0))))
    df["flag_ewma"] = df["rr_mdr_positive"] > (ewma_mean + 3 * ewma_sd.fillna(np.sqrt(ewma_mean.clip(lower=0))))
    residual = (df["rr_mdr_positive"] - rolling.fillna(prior).fillna(0)).fillna(0)
    def _cusum(series: pd.Series) -> pd.Series:
        values=[]; s=0.0
        scale=max(float(series.std(ddof=0)),1.0); k=0.5*scale; h=5*scale
        for value in series:
            s=max(0.0, s + float(value) - k)
            values.append(s > h)
            if s > h: s=0.0
        return pd.Series(values, index=series.index)
    df["flag_cusum"] = residual.groupby(df["geography_id"], group_keys=False).apply(_cusum).reset_index(level=0, drop=True)
    df["flag_ai"] = df["rr_mdr_positive"] > df["poisson_upper_ai"]
    df["flag_operational"] = df["rr_mdr_positive"] > df["poisson_upper_operational"]
    detector_cols = ["flag_persistence", "flag_seasonal_naive", "flag_shewhart", "flag_ewma", "flag_cusum"]
    df["conventional_detector_agreement"] = df[detector_cols].fillna(False).sum(axis=1)
    return df


def comparison_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for col in [c for c in df.columns if c.startswith("flag_")]:
        rows.append({"detector": col.replace("flag_", ""), "alerts": int(df[col].fillna(False).sum()), "alert_fraction": float(df[col].fillna(False).mean())})
    return pd.DataFrame(rows)
