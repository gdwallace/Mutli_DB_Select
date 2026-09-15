from __future__ import annotations

import json
import socket
from functools import lru_cache
from pathlib import Path

from flask import Flask, jsonify, render_template

ROOT = Path(__file__).resolve().parent
SERVERS_PATH = ROOT / "servers.json"

app = Flask(__name__)


def load_server_catalog() -> list[dict]:
    return json.loads(SERVERS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def resolve_ip(host: str) -> str | None:
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


def servers_with_addresses() -> list[dict]:
    servers = []
    for server in load_server_catalog():
        resolved = resolve_ip(server["host"])
        servers.append(
            {
                **server,
                "ip": resolved or server.get("ip") or "—",
            }
        )
    return servers


@app.get("/")
def index():
    servers = servers_with_addresses()
    return render_template("index.html", servers=servers)


@app.get("/api/servers")
def api_servers():
    return jsonify(servers_with_addresses())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
