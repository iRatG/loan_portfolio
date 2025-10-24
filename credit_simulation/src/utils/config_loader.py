import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import toml


def get_project_root(start_path: Optional[Path] = None) -> Path:
    """Attempt to locate project root by finding a parent that contains 'sql' directory.
    Falls back to current working directory.
    """
    path = start_path or Path(__file__).resolve()
    for parent in [path] + list(path.parents):
        candidate = parent if parent.is_dir() else parent.parent
        if (candidate / "sql").exists():
            return candidate
    return Path.cwd()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        cfg = toml.load(f)
    return cfg


def load_settings(config_path: Path):
    """Load and validate settings from TOML into Pydantic model."""
    from .settings import AppSettings

    cfg = load_config(config_path)
    return AppSettings(**cfg)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logging.getLogger(__name__).info("Saved JSON report to %s", path)
