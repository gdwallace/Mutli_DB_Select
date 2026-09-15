from unittest.mock import patch

from app import app, load_server_catalog
from sql import DATABASE_LIST_QUERY, QueryError, list_databases, normalize_select


PROD_CREDS = {"prod": {"username": "prod-user", "password": "prod-secret"}}
STAGE_CREDS = {"stage": {"username": "stage-user", "password": "stage-secret"}}
BOTH_CREDS = {**PROD_CREDS, **STAGE_CREDS}


def test_index_lists_each_server_name_and_host():
    response = app.test_client().get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Load databases" in page
    assert "Production credentials" in page
    assert "Staging credentials" in page
    assert 'id="sql-query"' in page
    for server in load_server_catalog():
        assert server["name"] in page
        if server.get("host"):
            assert server["host"] in page
        assert 'type="checkbox"' in page


def test_api_servers_returns_catalog_with_ips():
    catalog = load_server_catalog()
    response = app.test_client().get("/api/servers")
    payload = response.get_json()
    ids = {server["id"] for server in payload}
    by_id = {server["id"]: server for server in payload}

    assert response.status_code == 200
    assert len(payload) == len(catalog)
    assert ids == {server["id"] for server in catalog}
    assert all(server.get("ip") for server in payload)
    assert by_id["sql-butterfly"]["environment"] == "prod"
    assert by_id["sql01-staging"]["environment"] == "stage"


def test_api_databases_requires_a_server_selection():
    response = app.test_client().post(
        "/api/databases",
        json={"credentials": PROD_CREDS},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Select at least one server."


def test_api_databases_rejects_unknown_servers():
    response = app.test_client().post(
        "/api/databases",
        json={"servers": ["not-a-server"], "credentials": PROD_CREDS},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Unknown server selection."


def test_api_databases_requires_prod_credentials_for_prod_servers():
    response = app.test_client().post(
        "/api/databases",
        json={"servers": ["sql-butterfly"]},
    )
    assert response.status_code == 400
    assert (
        response.get_json()["error"]
        == "SQL username and password are required for production."
    )


def test_api_databases_requires_stage_credentials_for_stage_servers():
    response = app.test_client().post(
        "/api/databases",
        json={"servers": ["sql01-staging"], "credentials": PROD_CREDS},
    )
    assert response.status_code == 400
    assert (
        response.get_json()["error"]
        == "SQL username and password are required for staging."
    )


@patch("app.list_databases_for_servers")
def test_api_databases_uses_matching_environment_credentials(mock_list):
    mock_list.return_value = []

    response = app.test_client().post(
        "/api/databases",
        json={
            "servers": ["sql-butterfly", "sql01-staging"],
            "credentials": BOTH_CREDS,
        },
    )

    assert response.status_code == 200
    selected = mock_list.call_args.args[0]
    credentials = mock_list.call_args.args[1]
    assert [server["id"] for server in selected] == [
        "sql-butterfly",
        "sql01-staging",
    ]
    assert credentials["prod"]["username"] == "prod-user"
    assert credentials["stage"]["username"] == "stage-user"


@patch("sql.pymssql")
def test_list_databases_runs_sys_databases_query(mock_pymssql):
    cursor = mock_pymssql.connect.return_value.cursor.return_value
    cursor.fetchall.return_value = [("Appian",), ("master",)]

    result = list_databases(
        {
            "id": "sql-butterfly",
            "name": "Butterfly",
            "host": "sql-butterfly.appian.trimblemaps.com",
            "ip": "192.168.224.66",
            "environment": "prod",
        },
        PROD_CREDS["prod"],
    )

    cursor.execute.assert_called_once_with(DATABASE_LIST_QUERY)
    assert result["ok"] is True
    assert result["environment"] == "prod"
    assert result["databases"] == [
        {"name": "Appian", "system": False},
        {"name": "master", "system": True},
    ]


def test_normalize_select_accepts_select_and_cte():
    assert normalize_select("  SELECT 1;  ") == "SELECT 1"
    assert normalize_select("WITH x AS (SELECT 1 AS n) SELECT n FROM x").startswith(
        "WITH x AS"
    )


def test_normalize_select_rejects_non_select():
    for query in (
        "",
        "INSERT INTO t VALUES (1)",
        "SELECT 1; DROP TABLE t",
        "UPDATE t SET a = 1",
        "SELECT * INTO copy FROM t",
    ):
        try:
            normalize_select(query)
        except QueryError:
            continue
        raise AssertionError(f"expected QueryError for {query!r}")


def test_api_query_requires_a_select_and_databases():
    missing_db = app.test_client().post(
        "/api/query",
        json={"query": "SELECT 1", "credentials": PROD_CREDS},
    )
    assert missing_db.status_code == 400
    assert missing_db.get_json()["error"] == "Select at least one database."

    bad_sql = app.test_client().post(
        "/api/query",
        json={
            "query": "DELETE FROM t",
            "databases": [{"serverId": "sql-butterfly", "name": "Appian"}],
            "credentials": PROD_CREDS,
        },
    )
    assert bad_sql.status_code == 400
    assert bad_sql.get_json()["error"] == "Only SELECT statements are allowed."


@patch("app.run_select_on_targets")
def test_api_query_runs_against_selected_databases(mock_run):
    mock_run.return_value = [
        {
            "serverId": "sql-butterfly",
            "serverName": "Butterfly",
            "database": "Appian",
            "ok": True,
            "columns": ["name"],
            "rows": [["ok"]],
            "rowCount": 1,
            "truncated": False,
            "error": None,
        }
    ]

    response = app.test_client().post(
        "/api/query",
        json={
            "query": "SELECT name FROM dbo.Something",
            "databases": [{"serverId": "sql-butterfly", "name": "Appian"}],
            "credentials": PROD_CREDS,
        },
    )

    assert response.status_code == 200
    targets, query, credentials = mock_run.call_args.args
    assert query == "SELECT name FROM dbo.Something"
    assert targets[0][0]["id"] == "sql-butterfly"
    assert targets[0][1] == "Appian"
    assert credentials["prod"]["password"] == "prod-secret"
    assert response.get_json()["results"][0]["rows"] == [["ok"]]
