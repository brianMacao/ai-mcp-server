from ai_mcp_server.application import endpoint_service
from ai_mcp_server.storage.db import connect, db_path


def test_add_list_remove():
    ep = endpoint_service.add_endpoint("test", "https://example.com/v1", "sk-secret")
    assert ep.id > 0
    items = endpoint_service.list_endpoints()
    assert len(items) == 1 and items[0].name == "test"

    # api_key must be encrypted at rest
    p = db_path()
    raw = p.read_bytes()
    assert b"sk-secret" not in raw, "api_key leaked in cleartext"

    with connect() as conn:
        from ai_mcp_server.storage import dao
        decrypted = dao.get_endpoint_api_key(conn, ep.id)
    assert decrypted == "sk-secret"

    assert endpoint_service.remove_endpoint("test") is True
    assert endpoint_service.list_endpoints() == []
