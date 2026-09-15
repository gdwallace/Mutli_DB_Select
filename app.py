from __future__ import annotations

import ipaddress
import json
import os
import socket
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from sql import (
    ENVIRONMENTS,
    QueryError,
    assert_database_name,
    list_databases_for_servers,
    matching_query_results,
    normalize_select,
    run_select_on_targets,
)

ROOT = Path(__file__).resolve().parent
SERVERS_PATH = ROOT / "servers.json"
ENV_LABELS = {"prod": "production", "stage": "staging"}

load_dotenv(ROOT / ".env")

app = Flask(__name__)


def load_server_catalog() -> list[dict]:
    raw = json.loads(SERVERS_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        servers = []
        for env in ENVIRONMENTS:
            for server in raw.get(env) or []:
                servers.append({**server, "environment": env})
        return servers
    return raw


def servers_by_environment() -> dict[str, list[dict]]:
    grouped = {env: [] for env in ENVIRONMENTS}
    for server in servers_with_addresses():
        grouped[server["environment"]].append(server)
    return grouped


@lru_cache(maxsize=32)
def resolve_ip(host: str) -> str | None:
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


def servers_with_addresses() -> list[dict]:
    servers = []
    for server in load_server_catalog():
        host = server.get("host")
        resolved = resolve_ip(host) if host else None
        environment = server.get("environment") if server.get("environment") in ENVIRONMENTS else "prod"
        servers.append(
            {
                **server,
                "host": host or "",
                "ip": resolved or server.get("ip") or "—",
                "environment": environment,
            }
        )
    return servers


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _selected_servers(payload: dict) -> list[dict]:
    selected_ids = payload.get("servers") or []
    if not isinstance(selected_ids, list) or not selected_ids:
        raise QueryError("Select at least one server.")
    if not all(isinstance(server_id, str) and server_id for server_id in selected_ids):
        raise QueryError("Select at least one server.")

    catalog = {server["id"]: server for server in servers_with_addresses()}
    if any(server_id not in catalog for server_id in selected_ids):
        raise QueryError("Unknown server selection.")
    return [catalog[server_id] for server_id in selected_ids]


def parse_env_credentials(payload: dict, environments: set[str] | list[str]) -> dict:
    provided = payload.get("credentials") or {}
    if not isinstance(provided, dict):
        provided = {}

    parsed = {}
    missing = []
    for env in ENVIRONMENTS:
        if env not in environments:
            continue
        block = provided.get(env) or {}
        if not isinstance(block, dict):
            block = {}
        username = (
            block.get("username") or os.environ.get(f"MSSQL_{env.upper()}_USER") or ""
        ).strip() or None
        password = block.get("password") or os.environ.get(f"MSSQL_{env.upper()}_PASSWORD") or None
        if isinstance(password, str):
            password = password or None
        windows_auth = _truthy(block.get("windows_auth")) or _truthy(
            os.environ.get(f"MSSQL_{env.upper()}_WINDOWS_AUTH")
        )
        if not windows_auth and (not username or not password):
            missing.append(env)
        parsed[env] = {
            "username": username,
            "password": password,
            "windows_auth": windows_auth,
        }

    if missing:
        labels = " and ".join(ENV_LABELS[env] for env in missing)
        raise QueryError(f"SQL username and password are required for {labels}.")
    return parsed


def _error_response(message: str, status: int = 400):
    return jsonify({"error": message}), status


@app.get("/")
def index():
    return render_template("index.html", servers_by_env=servers_by_environment())


@app.get("/api/servers")
def api_servers():
    return jsonify(servers_with_addresses())


@app.post("/api/databases")
def api_databases():
    payload = request.get_json(silent=True) or {}
    try:
        selected = _selected_servers(payload)
        credentials = parse_env_credentials(
            payload, {server["environment"] for server in selected}
        )
    except QueryError as exc:
        return _error_response(str(exc))

    return jsonify({"results": list_databases_for_servers(selected, credentials)})


@app.post("/api/query")
def api_query():
    payload = request.get_json(silent=True) or {}
    try:
        query = normalize_select(payload.get("query") or "")
        raw_targets = payload.get("databases") or []
        if not isinstance(raw_targets, list) or not raw_targets:
            raise QueryError("Select at least one database.")

        catalog = {server["id"]: server for server in servers_with_addresses()}
        targets: list[tuple[dict, str]] = []
        for item in raw_targets:
            if not isinstance(item, dict):
                raise QueryError("Invalid database selection.")
            server_id = item.get("serverId")
            if server_id not in catalog:
                raise QueryError("Unknown server selection.")
            targets.append((catalog[server_id], assert_database_name(item.get("name"))))

        credentials = parse_env_credentials(
            payload, {server["environment"] for server, _database in targets}
        )
    except QueryError as exc:
        return _error_response(str(exc))

    return jsonify(
        {"results": matching_query_results(run_select_on_targets(targets, query, credentials))}
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
