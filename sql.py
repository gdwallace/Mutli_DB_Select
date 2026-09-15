from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

DATABASE_LIST_QUERY = "SELECT name FROM sys.databases ORDER BY name"
SYSTEM_DATABASES = frozenset({"master", "model", "msdb", "tempdb"})
LOGIN_TIMEOUT_SECONDS = 8
QUERY_TIMEOUT_SECONDS = 15


try:
    import pymssql
except ImportError:  # pragma: no cover
    pymssql = None


def connection_target(server: dict) -> str:
    return server.get("host") or server.get("ip") or ""


def connect(server: dict, username: str | None, password: str | None, windows_auth: bool):
    if pymssql is None:
        raise RuntimeError("pymssql is not installed")

    target = connection_target(server)
    if not target:
        raise ValueError("Server is missing a host name and IP")

    kwargs = {
        "server": target,
        "database": "master",
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


def _safe_error(exc: BaseException, password: str | None) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    if password:
        text = text.replace(password, "********")
    return text


def list_databases(
    server: dict,
    username: str | None,
    password: str | None,
    windows_auth: bool,
) -> dict:
    result = {
        "id": server["id"],
        "name": server["name"],
        "host": server.get("host") or "",
        "ip": server.get("ip") or "",
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


def list_databases_for_servers(
    servers: list[dict],
    username: str | None,
    password: str | None,
    windows_auth: bool,
) -> list[dict]:
    if not servers:
        return []

    results_by_id: dict[str, dict] = {}
    workers = min(8, len(servers))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(list_databases, server, username, password, windows_auth): server[
                "id"
            ]
            for server in servers
        }
        for future in as_completed(futures):
            server_id = futures[future]
            results_by_id[server_id] = future.result()

    return [results_by_id[server["id"]] for server in servers]
