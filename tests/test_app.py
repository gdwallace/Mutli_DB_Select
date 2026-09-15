from unittest.mock import patch

from app import app, load_server_catalog
from sql import (
    DATABASE_LIST_QUERY,
    QueryError,
    is_ignored_database,
    list_databases,
    matching_query_results,
    normalize_select,
)


PROD_CREDS = {"prod": {"username": "prod-user", "password": "prod-secret"}}
STAGE_CREDS = {"stage": {"username": "stage-user", "password": "stage-secret"}}
BOTH_CREDS = {**PROD_CREDS, **STAGE_CREDS}


def test_index_lists_each_server_name_and_host():
    response = app.test_client().get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Load databases" in page
    assert 'id="prod-heading"' in page
    assert 'id="stage-heading"' in page
    assert 'id="prod-username"' in page
    assert 'id="stage-username"' in page
    assert 'id="sql-query"' in page
    assert "workspace" in page
    assert "database-scroll" in page
    assert "results-scroll" in page
    assert 'id="export-csv"' in page
    for server in load_server_catalog():
        assert server["name"] in page
        if server.get("host"):
            assert server["host"] in page
        assert 'type="checkbox"' in page


def test_catalog_is_split_into_prod_and_stage():
    catalog = load_server_catalog()
    by_env = {}
    for server in catalog:
        by_env.setdefault(server["environment"], []).append(server["id"])

    assert by_env["prod"] == [
        "sql-butterfly",
        "sql-tadpole",
        "sql-milkyway",
        "sql-fireworks",
        "law-sql01",
        "10-228-2-38",
        "192-168-224-61",
    ]
    assert by_env["stage"] == ["sql01-staging", "law-sql02-staging"]


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
    cursor.fetchall.return_value = [
        ("Appian",),
        ("master",),
        ("DBA",),
        ("Hangfire",),
        ("HangfireJobs",),
        ("Hydra",),
        ("HydraTest",),
        ("msdb",),
        ("msdb_oldstage",),
        ("model",),
        ("PNET",),
        ("PNET_APP",),
        ("tempdb",),
    ]

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
    assert result["databases"] == [{"name": "Appian", "system": False}]


def test_ignored_database_patterns():
    ignored = [
        "master",
        "MODEL",
        "msdb",
        "tempdb",
        "DBA",
        "dba",
        "Hangfire",
        "HangfireProd",
        "Hydra",
        "Hydra_QA",
        "msdb_oldstage",
        "PNET",
        "PNET_MAPS",
    ]
    kept = ["Appian", "Law", "masterdata"]
    for name in ignored:
        assert is_ignored_database(name), name
    for name in kept:
        assert not is_ignored_database(name), name


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


@patch("app.run_select_on_targets")
def test_api_query_skips_ignored_databases(mock_run):
    mock_run.return_value = []

    response = app.test_client().post(
        "/api/query",
        json={
            "query": "SELECT 1",
            "databases": [
                {"serverId": "sql-butterfly", "name": "master"},
                {"serverId": "sql-butterfly", "name": "HangfireJobs"},
                {"serverId": "sql-butterfly", "name": "Appian"},
            ],
            "credentials": PROD_CREDS,
        },
    )

    assert response.status_code == 200
    targets = mock_run.call_args.args[0]
    assert [database for _server, database in targets] == ["Appian"]


def test_matching_query_results_keeps_hits_and_drops_missing_objects():
    visible = matching_query_results(
        [
            {
                "database": "MissingTable",
                "ok": False,
                "rowCount": 0,
                "rows": [],
                "error": "Invalid object name 'dbo.Foo'.",
            },
            {
                "database": "EmptyTable",
                "ok": True,
                "rowCount": 0,
                "rows": [],
                "error": None,
            },
            {
                "database": "Appian",
                "ok": True,
                "rowCount": 1,
                "rows": [["found"]],
                "error": None,
            },
            {
                "database": "Denied",
                "ok": False,
                "rowCount": 0,
                "rows": [],
                "error": "Login failed for user 'prod-user'.",
            },
        ]
    )
    assert [result["database"] for result in visible] == ["Appian", "Denied"]


@patch("app.run_select_on_targets")
def test_api_query_omits_missing_table_errors(mock_run):
    mock_run.return_value = [
        {
            "serverId": "sql-tadpole",
            "serverName": "Tadpole",
            "database": "OtherDb",
            "ok": False,
            "columns": [],
            "rows": [],
            "rowCount": 0,
            "truncated": False,
            "error": "Invalid object name 'dbo.Something'.",
        },
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
        },
    ]

    response = app.test_client().post(
        "/api/query",
        json={
            "query": "SELECT name FROM dbo.Something",
            "databases": [
                {"serverId": "sql-tadpole", "name": "OtherDb"},
                {"serverId": "sql-butterfly", "name": "Appian"},
            ],
            "credentials": PROD_CREDS,
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert [result["database"] for result in payload["results"]] == ["Appian"]
