from __future__ import annotations

import ipaddress
import json
import os
import socket
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from sql import list_databases_for_servers

ROOT = Path(__file__).resolve().parent
SERVERS_PATH = ROOT / "servers.json"

load_dotenv(ROOT / ".env")

app = Flask(__name__)


def load_server_catalog() -> list[dict]:
    return json.loads(SERVERS_PATH.read_text(encoding="utf-8"))


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
        servers.append(
            {
                **server,
                "host": host or "",
                "ip": resolved or server.get("ip") or "—",
            }
        )
    return servers


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@app.get("/")
def index():
    servers = servers_with_addresses()
    return render_template("index.html", servers=servers)


@app.get("/api/servers")
def api_servers():
    return jsonify(servers_with_addresses())


@app.post("/api/databases")
def api_databases():
    payload = request.get_json(silent=True) or {}
    selected_ids = payload.get("servers") or []
    if not isinstance(selected_ids, list) or not selected_ids:
        return jsonify({"error": "Select at least one server."}), 400
    if not all(isinstance(server_id, str) and server_id for server_id in selected_ids):
        return jsonify({"error": "Select at least one server."}), 400

    catalog = {server["id"]: server for server in servers_with_addresses()}
    if any(server_id not in catalog for server_id in selected_ids):
        return jsonify({"error": "Unknown server selection."}), 400

    windows_auth = _truthy(payload.get("windows_auth")) or _truthy(
        os.environ.get("MSSQL_WINDOWS_AUTH")
    )
    username = (payload.get("username") or os.environ.get("MSSQL_USER") or "").strip() or None
    password = payload.get("password") or os.environ.get("MSSQL_PASSWORD") or None
    if isinstance(password, str):
        password = password or None

    if not windows_auth and (not username or not password):
        return jsonify({"error": "SQL username and password are required."}), 400

    selected = [catalog[server_id] for server_id in selected_ids]
    return jsonify(
        {
            "results": list_databases_for_servers(
                selected, username, password, windows_auth
            )
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
