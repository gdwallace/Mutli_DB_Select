from app import app, load_server_catalog


def test_index_lists_each_server_name_and_host():
    response = app.test_client().get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    for server in load_server_catalog():
        assert server["name"] in page
        assert server["host"] in page
        assert 'type="checkbox"' in page


def test_api_servers_returns_catalog_with_ips():
    response = app.test_client().get("/api/servers")
    payload = response.get_json()
    hosts = {server["host"] for server in payload}

    assert response.status_code == 200
    assert len(payload) == 5
    assert hosts == {
        "sql-butterfly.appian.trimblemaps.com",
        "sql-tadpole.appian.trimblemaps.com",
        "sql-milkyway.appian.trimblemaps.com",
        "sql-fireworks.appian.trimblemaps.com",
        "law-sql01.appian.trimblemaps.com",
    }
    assert all(server.get("ip") for server in payload)
