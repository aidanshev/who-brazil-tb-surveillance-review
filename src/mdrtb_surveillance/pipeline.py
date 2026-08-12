from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import pandas as pd
from .country.registry import load_country_adapter
from .data_quality import grade_periods, summarize_data_quality
from .models import fit_all
from .benchmark import add_control_methods, comparison_summary
from .alerts import classify_alerts
from .provenance import file_sha256, write_json
from . import db


def run_country_pipeline(project_root: Path, config: dict[str, Any], release_id: str, data_vintage: str) -> Path:
    adapter=load_country_adapter(config)
    configured_code=str(config.get("country",{}).get("code","")).upper()
    if configured_code and configured_code != adapter.country_code.upper():
        raise ValueError(f"Configured country code {configured_code} does not match adapter {adapter.country_code}")
    config.setdefault("runtime", {})["data_vintage"] = data_vintage
    raw_paths=adapter.acquire(config,project_root)
    standardized=adapter.standardize(raw_paths,config,project_root)
    aggregated=adapter.aggregate(standardized,config,project_root)
    periods=grade_periods(aggregated,config)
    predictions,metrics,ai_names=fit_all(periods,config)
    predictions=add_control_methods(predictions,config)
    alerts=classify_alerts(predictions,config,release_id)
    run_dir=project_root/config["storage"]["run_root"]/release_id
    run_dir.mkdir(parents=True,exist_ok=True)
    
    try:
        standardized.to_parquet(run_dir/"standardized_records.parquet",index=False)
    except ImportError:
        standardized.to_csv(run_dir/"standardized_records.csv.gz",index=False,compression="gzip")
    periods.to_csv(run_dir/"data_quality_periods.csv",index=False)
    predictions.to_csv(run_dir/"predictions.csv",index=False)
    metrics.to_csv(run_dir/"model_metrics.csv",index=False)
    comparison_summary(predictions).to_csv(run_dir/"detector_comparison.csv",index=False)
    alerts.to_csv(run_dir/"alerts.csv",index=False)
    source_manifest={
      "release_id":release_id,"data_vintage":data_vintage,"created_at":datetime.now(timezone.utc).isoformat(),
      "evidence_mode":config["project"]["evidence_mode"],"source":adapter.source_description(config),
      "files":[{"path":str(p.relative_to(project_root)),"sha256":file_sha256(p),"size_bytes":p.stat().st_size} for p in raw_paths],
    }
    write_json(run_dir/"source_manifest.json",source_manifest)
    summary={
      "release_id":release_id,"data_vintage":data_vintage,"evidence_mode":config["project"]["evidence_mode"],
      "raw_files":len(raw_paths),"standardized_records":int(len(standardized)),"geographies":int(periods["geography_id"].nunique()),
      "periods":int(len(periods)),"alerts_by_tier":alerts["tier"].value_counts().sort_index().to_dict(),
      "signals":alerts["signal_type"].value_counts().to_dict(),"data_quality":summarize_data_quality(periods),"ai_models":ai_names,
      "safe_use":"Review prompts only; no autonomous outbreak declaration or clinical decision-making."
    }
    write_json(run_dir/"run_summary.json",summary)
    database=project_root/config["storage"]["database_path"]
    conn=db.connect(database)
    db.upsert_release(conn,release_id,data_vintage,status="generated",country_code=adapter.country_code,notes=config["project"]["evidence_mode"])
    db.replace_alerts(conn,alerts)
    conn.close()
    return run_dir


def run_brazil_pipeline(project_root: Path, config: dict[str, Any], release_id: str, data_vintage: str) -> Path:
    """Backward-compatible Brazil reference wrapper."""
    return run_country_pipeline(project_root,config,release_id,data_vintage)
