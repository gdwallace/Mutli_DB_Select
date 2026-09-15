from unittest.mock import patch

from app import app, load_server_catalog
from sql import DATABASE_LIST_QUERY, list_databases


def test_index_lists_each_server_name_and_host():
    response = app.test_client().get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Load databases" in page
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

    assert response.status_code == 200
    assert len(payload) == len(catalog)
    assert ids == {server["id"] for server in catalog}
    assert all(server.get("ip") for server in payload)
    assert {
        "10-228-2-38",
        "192-168-224-61",
        "sql01-staging",
        "law-sql02-staging",
    }.issubset(ids)


def test_api_databases_requires_a_server_selection():
    response = app.test_client().post(
        "/api/databases",
        json={"username": "user", "password": "secret"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Select at least one server."


def test_api_databases_rejects_unknown_servers():
    response = app.test_client().post(
        "/api/databases",
        json={
            "servers": ["not-a-server"],
            "username": "user",
            "password": "secret",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Unknown server selection."


def test_api_databases_requires_credentials():
    response = app.test_client().post(
        "/api/databases",
        json={"servers": ["sql-butterfly"]},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "SQL username and password are required."


@patch("app.list_databases_for_servers")
def test_api_databases_queries_selected_servers(mock_list):
    mock_list.return_value = [
        {
            "id": "sql-butterfly",
            "name": "Butterfly",
            "ok": True,
            "databases": [{"name": "Appian", "system": False}],
            "error": None,
        }
    ]

    response = app.test_client().post(
        "/api/databases",
        json={
            "servers": ["sql-butterfly"],
            "username": "user",
            "password": "secret",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results"][0]["databases"][0]["name"] == "Appian"
    selected = mock_list.call_args.args[0]
    assert [server["id"] for server in selected] == ["sql-butterfly"]
    assert mock_list.call_args.args[1:] == ("user", "secret", False)


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
        },
        "user",
        "secret",
        False,
    )

    cursor.execute.assert_called_once_with(DATABASE_LIST_QUERY)
    assert result["ok"] is True
    assert result["databases"] == [
        {"name": "Appian", "system": False},
        {"name": "master", "system": True},
    ]
