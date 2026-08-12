from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

try:
    from lightgbm import LGBMRegressor
except Exception:  # pragma: no cover
    LGBMRegressor = None


@dataclass
class ModelResult:
    predictions: pd.DataFrame
    metrics: pd.DataFrame
    model_name: str


def _features(frame: pd.DataFrame, target: str, config: dict[str, Any]) -> pd.DataFrame:
    df = frame.sort_values(["geography_id", "period_start"]).copy()
    grouped = df.groupby("geography_id", group_keys=False)
    for lag in config["models"]["features"]["lags"]:
        df[f"{target}_lag_{lag}"] = grouped[target].shift(lag)
    for window in config["models"]["features"]["rolling_windows"]:
        df[f"{target}_rollmean_{window}"] = grouped[target].transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())
        df[f"{target}_rollstd_{window}"] = grouped[target].transform(lambda s: s.shift(1).rolling(window, min_periods=2).std())
    quarter = pd.PeriodIndex(df["period"], freq="Q").quarter
    df["quarter_sin"] = np.sin(2 * np.pi * quarter / 4)
    df["quarter_cos"] = np.cos(2 * np.pi * quarter / 4)
    df["time_index"] = df.groupby("geography_id").cumcount()
    return df


def _predict_baselines(df: pd.DataFrame, target: str) -> dict[str, pd.Series]:
    g = df.groupby("geography_id")[target]
    persistence = g.shift(1)
    seasonal = g.shift(4)
    rolling4 = g.transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
    ewma = g.transform(lambda s: s.shift(1).ewm(alpha=0.35, adjust=False, min_periods=1).mean())
    return {
        "persistence": persistence,
        "seasonal_naive": seasonal,
        "rolling_mean_4": rolling4,
        "ewma": ewma,
    }


def fit_predict_target(periods: pd.DataFrame, target: str, config: dict[str, Any]) -> ModelResult:
    df = _features(periods, target, config)
    baselines = _predict_baselines(df, target)
    for name, series in baselines.items():
        df[f"pred_{name}"] = series
    feature_cols = [c for c in df.columns if c.startswith(f"{target}_lag_") or c.startswith(f"{target}_roll")]
    feature_cols += ["quarter_sin", "quarter_cos", "time_index"]
    valid = df[feature_cols].notna().all(axis=1) & df[target].notna()
    unique_periods = sorted(df.loc[valid, "period_start"].unique())
    if len(unique_periods) < config["time"]["minimum_training_periods"]:
        raise ValueError(f"Insufficient periods for {target}: {len(unique_periods)}")
    holdout_n = int(config["time"]["holdout_periods"])
    cutoff = unique_periods[-holdout_n]
    train = valid & (df["period_start"] < cutoff)
    test = valid & (df["period_start"] >= cutoff)
    X_train = df.loc[train, feature_cols].astype(float)
    y_train = df.loc[train, target].astype(float).clip(lower=0)
    X_all = df.loc[valid, feature_cols].astype(float)

    poisson = make_pipeline(StandardScaler(), PoissonRegressor(alpha=1.0, max_iter=1000))
    poisson.fit(X_train, y_train)
    df.loc[valid, "pred_poisson_regression"] = np.maximum(poisson.predict(X_all), 0)

    if LGBMRegressor is not None and config["models"].get("ai_model") == "lightgbm":
        ai = LGBMRegressor(
            objective="poisson",
            n_estimators=150,
            learning_rate=0.035,
            num_leaves=15,
            min_child_samples=20,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=1.0,
            random_state=int(config["models"]["random_seed"]),
            verbosity=-1,
            n_jobs=1,
            force_col_wise=True,
        )
        ai_name = "lightgbm"
    else:
        ai = HistGradientBoostingRegressor(loss="poisson", max_iter=250, learning_rate=0.05, max_leaf_nodes=15, random_state=int(config["models"]["random_seed"]))
        ai_name = "hist_gradient_boosting"
    ai.fit(X_train, y_train)
    df.loc[valid, f"pred_{ai_name}"] = np.maximum(ai.predict(X_all), 0)

    metric_rows = []
    model_names = [*baselines.keys(), "poisson_regression", ai_name]
    for name in model_names:
        pred_col = f"pred_{name}"
        mask = test & df[pred_col].notna()
        if not mask.any():
            continue
        y = df.loc[mask, target].astype(float)
        pred = df.loc[mask, pred_col].astype(float)
        weights = np.maximum(df.loc[mask, "tested"].astype(float), 1) if target == "rr_mdr_positive" else np.ones(mask.sum())
        metric_rows.append({
            "target": target,
            "model": name,
            "holdout_start": str(pd.Timestamp(cutoff).date()),
            "n": int(mask.sum()),
            "mae": float(mean_absolute_error(y, pred)),
            "weighted_mae": float(np.average(np.abs(y - pred), weights=weights)),
            "bias": float((pred - y).mean()),
        })
    return ModelResult(df, pd.DataFrame(metric_rows), ai_name)


def _champion(metrics: pd.DataFrame, target: str) -> str:
    subset = metrics.loc[(metrics["target"] == target) & metrics["weighted_mae"].notna()].sort_values(["weighted_mae", "mae", "model"])
    if subset.empty:
        raise ValueError(f"No valid model metrics for {target}")
    return str(subset.iloc[0]["model"])

def fit_all(periods: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    tests = fit_predict_target(periods, "tested", config)
    positives = fit_predict_target(periods, "rr_mdr_positive", config)
    metrics = pd.concat([tests.metrics, positives.metrics], ignore_index=True)
    tests_champion = _champion(metrics, "tested")
    positives_champion = _champion(metrics, "rr_mdr_positive")
    key = ["geography_id", "geography_name", "period", "period_start"]
    merged = tests.predictions.copy()
    pos_cols = list(dict.fromkeys(key + [f"pred_{positives.model_name}", f"pred_{positives_champion}"]))
    rename = {f"pred_{positives.model_name}": "expected_positive_ai", f"pred_{positives_champion}": "expected_positive_model"}
    if positives.model_name == positives_champion:
        rename = {f"pred_{positives.model_name}": "expected_positive_ai"}
    pos_pred = positives.predictions[pos_cols].rename(columns=rename)
    merged = merged.merge(pos_pred, on=key, how="left", validate="one_to_one")
    if "expected_positive_model" not in merged:
        merged["expected_positive_model"] = merged["expected_positive_ai"]
    merged["expected_tests_ai"] = merged[f"pred_{tests.model_name}"]
    merged["expected_tests_model"] = merged[f"pred_{tests_champion}"]
    merged["expected_yield_ai"] = np.where(merged["expected_tests_ai"] > 0, merged["expected_positive_ai"] / merged["expected_tests_ai"], np.nan)
    merged["expected_yield_model"] = np.where(merged["expected_tests_model"] > 0, merged["expected_positive_model"] / merged["expected_tests_model"], np.nan)
    names = {
        "tests_ai": tests.model_name, "positives_ai": positives.model_name,
        "tests_champion": tests_champion, "positives_champion": positives_champion,
    }
    return merged, metrics, names
