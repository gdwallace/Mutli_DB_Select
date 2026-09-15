from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

DATABASE_LIST_QUERY = "SELECT name FROM sys.databases ORDER BY name"
SYSTEM_DATABASES = frozenset({"master", "model", "msdb", "tempdb"})
ENVIRONMENTS = ("prod", "stage")
LOGIN_TIMEOUT_SECONDS = 8
QUERY_TIMEOUT_SECONDS = 30
MAX_ROWS_PER_DATABASE = 500
MAX_QUERY_CHARS = 20000

_SELECT_START = re.compile(r"\A\s*(WITH|SELECT)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|"
    r"GRANT|REVOKE|BACKUP|RESTORE|KILL|SHUTDOWN|INTO)\b",
    re.IGNORECASE,
)
_MISSING_TARGET = re.compile(
    r"invalid (object|column) name|"
    r"cannot find the object|"
    r"could not find|"
    r"could not be bound|"
    r"does not exist|"
    r"unknown object|"
    r"invalid object",
    re.IGNORECASE,
)

try:
    import pymssql
except ImportError:  # pragma: no cover
    pymssql = None


class QueryError(ValueError):
    """Raised when a user query is missing or not a single SELECT."""


def connection_target(server: dict) -> str:
    return server.get("host") or server.get("ip") or ""


def environment_for(server: dict) -> str:
    env = server.get("environment") or "prod"
    return env if env in ENVIRONMENTS else "prod"


def credentials_for(server: dict, credentials_by_env: dict) -> dict:
    return credentials_by_env.get(environment_for(server)) or {}


def connect(
    server: dict,
    username: str | None,
    password: str | None,
    windows_auth: bool,
    database: str = "master",
):
    if pymssql is None:
        raise RuntimeError("pymssql is not installed")

    target = connection_target(server)
    if not target:
        raise ValueError("Server is missing a host name and IP")

    kwargs = {
        "server": target,
        "database": database,
        "login_timeout": LOGIN_TIMEOUT_SECONDS,
        "timeout": QUERY_TIMEOUT_SECONDS,
        "tds_version": "7.4",
        "appname": "Multi-DB Select",
    }
    if not windows_auth:
        if not username or not password:
            raise ValueError("SQL username and password are required")
        kwargs["user"] = username
        kwargs["password"] = password
    return pymssql.connect(**kwargs)


def _safe_error(exc: BaseException, secrets: list[str | None] | str | None) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    if isinstance(secrets, str) or secrets is None:
        secrets = [secrets]
    for secret in secrets:
        if secret:
            text = text.replace(secret, "********")
    return text


def _credential_parts(credentials: dict) -> tuple[str | None, str | None, bool]:
    username = credentials.get("username") or None
    password = credentials.get("password") or None
    windows_auth = bool(credentials.get("windows_auth"))
    return username, password, windows_auth


def normalize_select(sql: str) -> str:
    query = (sql or "").strip()
    if not query:
        raise QueryError("Enter a query.")
    if len(query) > MAX_QUERY_CHARS:
        raise QueryError("Query is too long.")
    query = query.rstrip().rstrip(";").strip()
    if not query:
        raise QueryError("Enter a query.")
    if ";" in query:
        raise QueryError("Run a single SELECT statement.")
    if not _SELECT_START.search(query) or _FORBIDDEN.search(query):
        raise QueryError("Only SELECT statements are allowed.")
    return query


def assert_database_name(name: object) -> str:
    if not isinstance(name, str):
        raise QueryError("Invalid database selection.")
    database = name.strip()
    if not database or len(database) > 128 or ";" in database or "\x00" in database:
        raise QueryError("Invalid database selection.")
    return database


def jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    return str(value)


def list_databases(server: dict, credentials: dict) -> dict:
    username, password, windows_auth = _credential_parts(credentials)
    result = {
        "id": server["id"],
        "name": server["name"],
        "host": server.get("host") or "",
        "ip": server.get("ip") or "",
        "environment": environment_for(server),
        "ok": False,
        "databases": [],
        "error": None,
    }
    try:
        conn = connect(server, username, password, windows_auth)
        try:
            cursor = conn.cursor()
            cursor.execute(DATABASE_LIST_QUERY)
            names = [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        result["error"] = _safe_error(exc, password)
        return result

    result["ok"] = True
    result["databases"] = [
        {"name": name, "system": str(name).lower() in SYSTEM_DATABASES}
        for name in names
    ]
    return result


def list_databases_for_servers(servers: list[dict], credentials_by_env: dict) -> list[dict]:
    if not servers:
        return []

    results_by_id: dict[str, dict] = {}
    workers = min(8, len(servers))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                list_databases, server, credentials_for(server, credentials_by_env)
            ): server["id"]
            for server in servers
        }
        for future in as_completed(futures):
            server_id = futures[future]
            results_by_id[server_id] = future.result()

    return [results_by_id[server["id"]] for server in servers]


def run_select(
    server: dict,
    database: str,
    query: str,
    credentials: dict,
    row_limit: int = MAX_ROWS_PER_DATABASE,
) -> dict:
    username, password, windows_auth = _credential_parts(credentials)
    result = {
        "serverId": server["id"],
        "serverName": server["name"],
        "environment": environment_for(server),
        "database": database,
        "ok": False,
        "columns": [],
        "rows": [],
        "rowCount": 0,
        "truncated": False,
        "error": None,
    }
    try:
        conn = connect(server, username, password, windows_auth, database=database)
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [col[0] for col in (cursor.description or [])]
            rows = []
            truncated = False
            for index, row in enumerate(cursor):
                if index >= row_limit:
                    truncated = True
                    break
                rows.append([jsonable(value) for value in row])
        finally:
            conn.close()
    except Exception as exc:
        result["error"] = _safe_error(exc, password)
        return result

    result.update(
        ok=True,
        columns=columns,
        rows=rows,
        rowCount=len(rows),
        truncated=truncated,
    )
    return result


def is_missing_target_error(error: str | None) -> bool:
    if not error:
        return False
    return bool(_MISSING_TARGET.search(error))


def matching_query_results(results: list[dict]) -> list[dict]:
    """Keep only databases that returned rows; skip missing-table/column errors."""
    visible = []
    for result in results:
        if result.get("ok"):
            if result.get("rowCount"):
                visible.append(result)
            continue
        if is_missing_target_error(result.get("error")):
            continue
        visible.append(result)
    return visible


def run_select_on_targets(
    targets: list[tuple[dict, str]],
    query: str,
    credentials_by_env: dict,
) -> list[dict]:
    if not targets:
        return []

    results: list[dict | None] = [None] * len(targets)
    workers = min(8, len(targets))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                run_select,
                server,
                database,
                query,
                credentials_for(server, credentials_by_env),
            ): index
            for index, (server, database) in enumerate(targets)
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return [item for item in results if item is not None]
