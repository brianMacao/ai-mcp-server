from ai_mcp_server.storage import crypto


def test_round_trip():
    enc = crypto.encrypt("sk-abc-123")
    assert isinstance(enc, bytes)
    assert b"sk-abc" not in enc
    assert crypto.decrypt(enc) == "sk-abc-123"


def test_unique_per_encryption():
    a = crypto.encrypt("x")
    b = crypto.encrypt("x")
    assert a != b  # Fernet includes nonce
    assert crypto.decrypt(a) == crypto.decrypt(b) == "x"
