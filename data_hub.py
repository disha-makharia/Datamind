"""
Local Data Hub (box 4 in the architecture slide).

- Loads CSV / JSON / Parquet / Excel files into DuckDB tables
- Builds a schema *catalog* (columns, types, sample values, ranges) that the
  Data Agent uses to pick tables and the SQL Agent uses to write queries
- Guards and executes SQL (read-only, known tables only, no file access)
"""
import re
import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import pandas as pd
import sqlglot
from sqlglot import exp

import config

SUPPORTED = {".csv", ".json", ".parquet", ".xlsx", ".xls"}
BLOCKED_FUNCTIONS = ("read_", "glob", "sniff_csv", "query_table", "getenv", "httpfs")
WRITE_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
               exp.Command, exp.Merge, exp.Copy, exp.Set, exp.Pragma, exp.Attach, exp.Detach)


def _table_name(raw: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z_]", "_", raw.strip()).lower().strip("_")
    return f"t_{name}" if name[:1].isdigit() else (name or "table")


def _parse_date_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Excel often stores dates as text; convert columns that fully parse as dates."""
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            sample = df[col].dropna().astype(str).head(50)
            if len(sample) and sample.str.match(r"^\d{4}-\d{2}-\d{2}").all():
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() == df[col].notna().sum():
                    df[col] = parsed.dt.date if (parsed.dt.time == pd.Timestamp(0).time()).all() else parsed
    return df


def _to_python(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


class DataHub:
    def __init__(self, db_path: str = ":memory:"):
        self.con = duckdb.connect(db_path)
        self._lock = threading.Lock()          # FastAPI may call from threads
        self._catalog: list[dict] | None = None
        self.sources: dict[str, str] = {}      # table -> file it came from
        self.paths: dict[str, Path] = {}       # table -> full path of that file

    # ------------------------------------------------------------ loading
    def load_file(self, path: str | Path) -> list[str]:
        path = Path(path)
        ext = path.suffix.lower()
        if ext not in SUPPORTED:
            raise ValueError(f"Unsupported file type {ext}. Supported: {sorted(SUPPORTED)}")
        p = str(path).replace("'", "''")
        created = []
        with self._lock:
            if ext in (".xlsx", ".xls"):
                for sheet, df in pd.read_excel(path, sheet_name=None).items():
                    if df.empty:
                        continue
                    df = _parse_date_columns(df)
                    name = _table_name(sheet)
                    self.con.register("_tmp_df", df)
                    self.con.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM _tmp_df')
                    self.con.unregister("_tmp_df")
                    created.append(name)
            else:
                reader = {".csv": "read_csv_auto", ".json": "read_json_auto",
                          ".parquet": "read_parquet"}[ext]
                name = _table_name(path.stem)
                self.con.execute(f"CREATE OR REPLACE TABLE \"{name}\" AS SELECT * FROM {reader}('{p}')")
                created.append(name)
            for t in created:
                self._clean_numeric_text(t)
                self._clean_date_text(t)
        for t in created:
            self.sources[t] = path.name
            self.paths[t] = path.resolve()
        self._catalog = None
        return created

    # text such as "17,524.02", "₹1,200", "$ 99.50" -> DOUBLE, so SUM/AVG work
    _NUMERIC_TEXT = r"^\s*[₹$€£]?\s*-?[0-9][0-9,]*(\.[0-9]+)?\s*$"

    def _clean_numeric_text(self, table: str) -> list[str]:
        """Convert VARCHAR columns whose every value is a formatted number. Caller holds the lock."""
        converted = []
        cols = self.con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=? AND data_type='VARCHAR'", [table]).fetchall()
        for (col,) in cols:
            q = f'"{col}"'
            non_null, bad, formatted = self.con.execute(
                f"SELECT count({q}), "
                f"count(*) FILTER (WHERE {q} IS NOT NULL AND NOT regexp_full_match({q}, ?)), "
                f"count(*) FILTER (WHERE regexp_matches({q}, '[,₹$€£]')) FROM \"{table}\"",
                [self._NUMERIC_TEXT]).fetchone()
            # all values numeric-looking, and at least some carry commas/currency
            # (plain digit strings like IDs or phone numbers are left alone)
            if non_null and not bad and formatted:
                self.con.execute(
                    f'CREATE OR REPLACE TABLE "{table}" AS SELECT * REPLACE ('
                    f"TRY_CAST(regexp_replace({q}, '[₹$€£,\\s]', '', 'g') AS DOUBLE) AS {q}) "
                    f'FROM "{table}"')
                converted.append(col)
        return converted

    _DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%m-%d-%Y", "%d.%m.%Y",
                     "%Y/%m/%d", "%d %b %Y", "%b %d, %Y"]

    def _clean_date_text(self, table: str) -> list[str]:
        """Convert text date columns to DATE when exactly one format fits every value.
        If several formats fit (e.g. every day is <= 12, so 02/03 could be Feb 3 or Mar 2)
        the column is left as text rather than guessing wrong. Caller holds the lock."""
        converted = []
        cols = self.con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=? AND data_type='VARCHAR'", [table]).fetchall()
        for (col,) in cols:
            q = f'"{col}"'
            non_null = self.con.execute(f'SELECT count({q}) FROM "{table}"').fetchone()[0]
            if not non_null:
                continue
            fits = []
            for f in self._DATE_FORMATS:
                bad = self.con.execute(
                    f"SELECT count(*) FROM \"{table}\" WHERE {q} IS NOT NULL "
                    f"AND try_strptime(trim({q}), ?) IS NULL", [f]).fetchone()[0]
                if bad == 0:
                    fits.append(f)
            if len(fits) == 1:
                self.con.execute(
                    f'CREATE OR REPLACE TABLE "{table}" AS SELECT * REPLACE ('
                    f"CAST(strptime(trim({q}), '{fits[0]}') AS DATE) AS {q}) FROM \"{table}\"")
                converted.append(col)
        return converted

    def load_directory(self, directory: str | Path) -> list[str]:
        tables = []
        for f in sorted(Path(directory).iterdir()):
            if f.is_file() and f.suffix.lower() in SUPPORTED:
                tables += self.load_file(f)
        return tables

    def is_uploaded(self, table: str) -> bool:
        p = self.paths.get(table)
        return bool(p) and config.UPLOAD_DIR.resolve() in p.parents

    def drop_table(self, table: str) -> None:
        """Only tables that came from user uploads can be removed."""
        if table not in self.list_tables():
            raise KeyError(table)
        if not self.is_uploaded(table):
            raise PermissionError("Only uploaded tables can be removed")
        path = self.paths[table]
        with self._lock:
            self.con.execute(f'DROP TABLE "{table}"')
        still_used = [t for t, p in self.paths.items() if p == path and t != table
                      and t in self.list_tables()]
        self.sources.pop(table, None)
        self.paths.pop(table, None)
        if not still_used and path.exists():
            path.unlink()
        self._catalog = None

    def preview(self, table: str, limit: int = 50) -> dict:
        if table not in self.list_tables():
            raise KeyError(table)
        with self._lock:
            cur = self.con.execute(f'SELECT * FROM "{table}" LIMIT {int(limit)}')
            columns = [d[0] for d in cur.description]
            rows = [[_to_python(v) for v in r] for r in cur.fetchall()]
        return {"table": table, "columns": columns, "rows": rows}

    # ------------------------------------------------------------ catalog
    def list_tables(self) -> list[str]:
        with self._lock:
            return [r[0] for r in self.con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main' "
                "ORDER BY table_name").fetchall()]

    def catalog(self, refresh: bool = False) -> list[dict]:
        """Rich schema description. Sample values matter: they tell the LLM that
        region is 'West' not 'west', and that dates span 2024-2025."""
        if self._catalog is not None and not refresh:
            return self._catalog
        out = []
        with self._lock:
            for (table,) in self.con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='main' "
                    "ORDER BY table_name").fetchall():
                row_count = self.con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                cols = []
                for name, dtype in self.con.execute(
                        "SELECT column_name, data_type FROM information_schema.columns "
                        "WHERE table_name=? ORDER BY ordinal_position", [table]).fetchall():
                    info = {"name": name, "type": dtype}
                    q = f'"{name}"'
                    if dtype in ("VARCHAR",):
                        n_distinct = self.con.execute(
                            f'SELECT COUNT(DISTINCT {q}) FROM "{table}"').fetchone()[0]
                        samples = [r[0] for r in self.con.execute(
                            f'SELECT DISTINCT {q} FROM "{table}" WHERE {q} IS NOT NULL LIMIT 12').fetchall()]
                        info["distinct"] = n_distinct
                        # low-cardinality columns: show ALL values so filters are exact
                        info["values" if n_distinct <= 12 else "examples"] = samples[:12 if n_distinct <= 12 else 3]
                    elif any(k in dtype for k in ("INT", "DOUBLE", "DECIMAL", "FLOAT", "DATE", "TIMESTAMP")):
                        lo, hi = self.con.execute(f'SELECT MIN({q}), MAX({q}) FROM "{table}"').fetchone()
                        info["min"], info["max"] = _to_python(lo), _to_python(hi)
                    cols.append(info)
                out.append({"table": table, "row_count": row_count, "columns": cols,
                            "source": self.sources.get(table, ""),
                            "uploaded": self.is_uploaded(table)})
        self._catalog = out
        return out

    def find_values(self, values: list[str], max_hits: int = 12) -> list[dict]:
        """Where do these literal values appear? Exact, case-insensitive match on text
        columns. Lets the Data agent see that '53-7769693' lives in orders.order_id."""
        hits = []
        values = [v for v in dict.fromkeys(v.strip() for v in values) if v][:8]
        if not values:
            return hits
        with self._lock:
            text_cols = self.con.execute(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema='main' AND data_type='VARCHAR'").fetchall()
            for value in values:
                for table, col in text_cols:
                    n = self.con.execute(
                        f'SELECT count(*) FROM "{table}" WHERE lower(trim("{col}")) = lower(?)',
                        [value]).fetchone()[0]
                    if n:
                        hits.append({"value": value, "table": table, "column": col, "rows": n})
                        if len(hits) >= max_hits:
                            return hits
        return hits

    def describe_tables(self, tables: list[str] | None = None) -> str:
        """Catalog rendered as compact text for prompts."""
        lines = []
        for t in self.catalog():
            if tables and t["table"] not in tables:
                continue
            tag = ", uploaded by the user" if t.get("uploaded") else ""
            lines.append(f'TABLE {t["table"]}  ({t["row_count"]:,} rows{tag})')
            for c in t["columns"]:
                extra = ""
                if "values" in c:
                    extra = f"  values={c['values']}"
                elif "examples" in c:
                    extra = f"  e.g. {c['examples']}"
                elif "min" in c:
                    extra = f"  range=[{c['min']} .. {c['max']}]"
                lines.append(f'  - {c["name"]} {c["type"]}{extra}')
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------ SQL
    def validate_sql(self, sql: str) -> str:
        """Raise ValueError if the SQL is unsafe. Returns the cleaned SQL."""
        sql = sql.strip().rstrip(";").strip()
        try:
            statements = sqlglot.parse(sql, read="duckdb")
        except sqlglot.errors.ParseError as e:
            raise ValueError(f"SQL parse error: {e}") from e
        if len(statements) != 1 or statements[0] is None:
            raise ValueError("Exactly one SQL statement is allowed")
        tree = statements[0]
        if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            raise ValueError("Only SELECT queries are allowed")
        if any(tree.find_all(*WRITE_NODES)):
            raise ValueError("Write/DDL operations are not allowed")
        for fn in tree.find_all(exp.Func):
            fname = (fn.sql_name() if not isinstance(fn, exp.Anonymous) else fn.name).lower()
            if fname.startswith(BLOCKED_FUNCTIONS):
                raise ValueError(f"Function {fname} is not allowed")
        known = set(self.list_tables())
        ctes = {c.alias_or_name for c in tree.find_all(exp.CTE)}
        for tbl in tree.find_all(exp.Table):
            if not tbl.name:  # table functions like range()
                continue
            if tbl.name not in known and tbl.name not in ctes:
                raise ValueError(f"Unknown table '{tbl.name}'. Available: {sorted(known)}")
        return sql

    def run_query(self, sql: str, limit: int = config.SQL_ROW_LIMIT) -> dict:
        sql = self.validate_sql(sql)
        with self._lock:
            cur = self.con.execute(sql)
            columns = [d[0] for d in cur.description]
            rows = cur.fetchmany(limit + 1)
        truncated = len(rows) > limit
        rows = [[_to_python(v) for v in r] for r in rows[:limit]]
        return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated}


# ---------------------------------------------------------------- singleton
_hub: DataHub | None = None


def get_hub() -> DataHub:
    global _hub
    if _hub is None:
        _hub = DataHub()
        _hub.load_directory(config.DATA_DIR)
        if config.UPLOAD_DIR.exists():
            _hub.load_directory(config.UPLOAD_DIR)
    return _hub


def set_hub(hub: DataHub) -> None:
    """For tests."""
    global _hub
    _hub = hub
