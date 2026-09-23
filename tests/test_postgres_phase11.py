from nascente_brasil.database.postgres import SCHEMAS, dsn, hashlib_sha


def test_database_schemas_are_complete():
    assert SCHEMAS == ("raw", "staging", "intermediate", "analytics", "metadata")


def test_postgres_dsn_can_be_overridden(monkeypatch):
    monkeypatch.setenv("NASCENTE_POSTGRES_DSN", "postgresql://example/test")
    assert dsn() == "postgresql://example/test"


def test_load_run_hash_is_deterministic():
    assert hashlib_sha({"b": 2, "a": 1}) == hashlib_sha({"a": 1, "b": 2})
