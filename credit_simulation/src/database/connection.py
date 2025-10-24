import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def get_engine(connection_string: str) -> Engine:
    engine = create_engine(connection_string, echo=False, future=True)
    return engine


def run_ddl_sqlite(engine: Engine, project_root: Path) -> None:
    ddl_path = project_root / "sql" / "create_tables.sql"
    if not ddl_path.exists():
        raise FileNotFoundError(f"DDL file not found: {ddl_path}")
    sql_text = ddl_path.read_text(encoding="utf-8")
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in sql_text.split(";"))):
            if stmt:
                conn.execute(text(stmt))
    logging.getLogger(__name__).info("Applied DDL from %s", ddl_path)


def run_sql_file(engine: Engine, sql_path: Path) -> None:
    """Execute SQL statements from a file (semicolon-separated)."""
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")
    sql_text = sql_path.read_text(encoding="utf-8")
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in sql_text.split(";"))):
            if stmt:
                conn.execute(text(stmt))
    logging.getLogger(__name__).info("Applied SQL from %s", sql_path)