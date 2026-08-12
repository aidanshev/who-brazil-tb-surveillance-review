from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from typing import Any
import yaml


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_country_config(project_root: Path, config_name: str = "brazil", mode: str = "production") -> dict[str, Any]:
    """Load base settings plus one country configuration.

    ``config_name`` is the filename stem under ``configs/``. The WHO layer is
    common and optional. Demonstration mode is currently the Brazil reference
    fixture and is applied only when explicitly requested.
    """
    config = load_yaml(project_root / "configs" / "base.yaml")
    country_path=project_root / "configs" / f"{config_name}.yaml"
    config = _deep_merge(config, load_yaml(country_path))
    who_path = project_root / "configs" / "who.yaml"
    if who_path.exists():
        config = _deep_merge(config, load_yaml(who_path))
    if mode == "demo":
        config = _deep_merge(config, load_yaml(project_root / "configs" / "demo.yaml"))
    if config.get("country",{}).get("code"):
        config.setdefault("project",{})["country_code"]=config["country"]["code"]
    return config


def load_config(project_root: Path, mode: str = "production") -> dict[str, Any]:
    """Backward-compatible loader for the Brazil reference implementation."""
    return load_country_config(project_root,"brazil",mode)
