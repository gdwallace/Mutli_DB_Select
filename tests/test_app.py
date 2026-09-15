from app import app, load_server_catalog


def test_index_lists_each_server_name_and_host():
    response = app.test_client().get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
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
