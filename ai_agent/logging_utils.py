import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Union


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_jsonl(file_path: Union[str, Path], record: Dict[str, Any]) -> None:
    path = Path(file_path)
    _ensure_parent(path)
    record = {
        **record,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_agent_interaction(
    file_path: Union[str, Path],
    *,
    question: str,
    success: bool,
    answer: Optional[str] = None,
    error: Optional[str] = None,
    latency_ms: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    rec: Dict[str, Any] = {
        "type": "agent_interaction",
        "success": success,
        "question": question,
    }
    if answer is not None:
        rec["answer"] = answer
        rec["answer_preview"] = answer[:200]
    if error is not None:
        rec["error"] = error
    if latency_ms is not None:
        rec["latency_ms"] = round(float(latency_ms), 1)
    if extra:
        rec.update(extra)
    append_jsonl(file_path, rec)


def log_sql_event(
    file_path: Union[str, Path],
    *,
    name: str,
    sql: str,
    success: bool,
    rowcount: int = 0,
    duration_ms: float = 0.0,
    error: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    rec: Dict[str, Any] = {
        "type": "sql",
        "name": name,
        "success": success,
        "rowcount": int(rowcount),
        "duration_ms": round(float(duration_ms), 1),
        "sql_preview": sql.strip().replace("\n", " ")[:300],
    }
    if error:
        rec["error"] = error
    if extra:
        rec.update(extra)
    append_jsonl(file_path, rec)
