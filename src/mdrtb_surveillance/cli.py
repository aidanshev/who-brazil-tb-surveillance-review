from __future__ import annotations
from pathlib import Path
import json
import typer
import uvicorn
from .config import load_config, load_country_config
from .pipeline import run_brazil_pipeline, run_country_pipeline
from .freeze import freeze_release, verify_release
from .provenance import write_json
from . import db
from .who import rebuild_who_layer

app=typer.Typer(help="Open WHO-Brazil MDR/RR-TB surveillance review platform")

@app.command()
def demo(project_root: Path=Path("."), release_id: str="brazil-demo-2024q4"):
    """Run the deterministic offline demonstration. Never use its outputs for inference."""
    project_root=project_root.resolve(); config=load_config(project_root,"demo")
    run_dir=run_brazil_pipeline(project_root,config,release_id,"demo-2024Q4")
    typer.echo(str(run_dir))

@app.command("run-country")
def run_country(project_root: Path=Path("."), config_name: str=typer.Option(...,help="Country config filename stem under configs/"), release_id: str=typer.Option(...), data_vintage: str=typer.Option(...)):
    """Run any implemented country adapter through the common surveillance pipeline."""
    project_root=project_root.resolve(); config=load_country_config(project_root,config_name,"production")
    run_dir=run_country_pipeline(project_root,config,release_id,data_vintage)
    typer.echo(str(run_dir))

@app.command("run-brazil")
def run_brazil(project_root: Path=Path("."), release_id: str="brazil-public-current", data_vintage: str="current"):
    """Download/import official public SINAN data and rebuild the Brazil layer."""
    project_root=project_root.resolve(); config=load_config(project_root,"production")
    run_dir=run_brazil_pipeline(project_root,config,release_id,data_vintage)
    typer.echo(str(run_dir))

@app.command()
def freeze(project_root: Path=Path("."), release_id: str=typer.Option(...), data_vintage: str=typer.Option(...), config_name: str="brazil"):
    project_root=project_root.resolve(); config=load_country_config(project_root,config_name,"demo" if "demo" in release_id else "production")
    run_dir=project_root/config["storage"]["run_root"]/release_id
    manifest=freeze_release(project_root,release_id,data_vintage,config,run_dir)
    conn=db.connect(project_root/config["storage"]["database_path"])
    db.upsert_release(conn,release_id,data_vintage,status="prospectively_frozen",country_code=str(config.get("country",{}).get("code","XXX")),manifest_sha256=manifest["manifest_sha256"],config_sha256=manifest["config_hash"],code_sha256=manifest["code_hash"],predictions_sha256=manifest["file_hashes"]["predictions.csv"])
    conn.close(); typer.echo(json.dumps(manifest,indent=2))

@app.command("verify-freeze")
def verify_freeze(project_root: Path=Path("."), release_id: str=typer.Option(...), config_name: str="brazil"):
    project_root=project_root.resolve(); config=load_country_config(project_root,config_name,"demo" if "demo" in release_id else "production")
    result=verify_release(project_root,release_id,config); typer.echo(json.dumps(result,indent=2));
    if not result["passed"]: raise typer.Exit(1)

@app.command("export-reviews")
def export_reviews(project_root: Path=Path("."), output: Path=Path("artifacts/analyst_reviews.csv")):
    project_root=project_root.resolve(); config=load_config(project_root,"production")
    conn=db.connect(project_root/config["storage"]["database_path"])
    frame=db.query_df(conn,"SELECT r.*, a.release_id, a.region_id, a.region_name, a.period, a.signal_type FROM analyst_reviews r JOIN alerts a USING(alert_uid) ORDER BY r.created_at")
    conn.close(); path=project_root/output; path.parent.mkdir(parents=True,exist_ok=True); frame.to_csv(path,index=False); typer.echo(str(path))

@app.command("run-who")
def run_who(project_root: Path=Path("."), who_repo: Path=typer.Option(...,help="Path to the official WHO Global TB Report data repository checkout")):
    """Rebuild the transparent WHO country report-card layer from raw official repository data."""
    project_root=project_root.resolve(); who_repo=who_repo.resolve()
    summary=rebuild_who_layer(project_root,who_repo)
    typer.echo(json.dumps(summary,indent=2,default=str))

@app.command("scaffold-country")
def scaffold_country(project_root: Path=Path("."), country_code: str=typer.Option(...,help="ISO3 code"), module_name: str=typer.Option(...,help="Python module name, for example peru"), class_name: str=typer.Option(...,help="Adapter class name, for example PeruAdapter")):
    """Create a fail-closed country adapter and configuration scaffold."""
    project_root=project_root.resolve(); code=country_code.upper().strip(); module=module_name.lower().replace("-","_").strip()
    if len(code)!=3 or not code.isalpha(): raise typer.BadParameter("country_code must be a three-letter ISO-style code")
    if not module.replace("_","").isalnum(): raise typer.BadParameter("module_name must contain letters, numbers, or underscores")
    country_dir=project_root/"src"/"mdrtb_surveillance"/"country"; country_dir.mkdir(parents=True,exist_ok=True)
    target=country_dir/f"{module}.py"
    if target.exists(): raise typer.BadParameter(f"Refusing to overwrite {target}")
    adapter=(
        "from __future__ import annotations\n"
        "from pathlib import Path\n"
        "from typing import Any\n"
        "import pandas as pd\n"
        "from .base import CountryAdapter\n\n\n"
        f"class {class_name}(CountryAdapter):\n"
        f"    country_code = \"{code}\"\n\n"
        "    def acquire(self, config: dict[str, Any], project_root: Path) -> list[Path]:\n"
        "        raise NotImplementedError(\"Implement immutable acquisition from an official public source\")\n\n"
        "    def standardize(self, raw_paths: list[Path], config: dict[str, Any], project_root: Path) -> pd.DataFrame:\n"
        "        raise NotImplementedError(\"Map source fields into the canonical surveillance schema\")\n\n"
        "    def aggregate(self, standardized: pd.DataFrame, config: dict[str, Any], project_root: Path) -> pd.DataFrame:\n"
        "        raise NotImplementedError(\"Aggregate to a complete geography-period panel without dropping missing periods\")\n\n"
        "    def source_description(self, config: dict[str, Any]) -> dict[str, Any]:\n"
        f"        return {{\"country_code\": \"{code}\", \"status\": \"scaffold\"}}\n"
    )
    target.write_text(adapter)
    config_path=project_root/"configs"/f"{module}.yaml"
    config_path.write_text(
        "country:\n"
        f"  code: {code}\n"
        f"  adapter: mdrtb_surveillance.country.{module}:{class_name}\n"
        "  source_mode: public\n"
        "  local_paths: []\n"
        "  aggregation_frequency: Q\n"
        "  allow_municipality_fallback: false\n"
    )
    typer.echo(json.dumps({"adapter":str(target),"config":str(config_path)},indent=2))

@app.command()
def serve(project_root: Path=Path("."), host: str="127.0.0.1", port: int=8000, reload: bool=False):
    from .web.app import create_app
    uvicorn.run(create_app(project_root.resolve()),host=host,port=port,reload=reload)

if __name__ == "__main__": app()
