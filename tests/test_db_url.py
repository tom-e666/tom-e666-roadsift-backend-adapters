from roadsift_adapters.db.session import normalize_async_postgres_url


def test_normalize_supabase_url():
    assert normalize_async_postgres_url("postgresql://u:p@host/db") == "postgresql+psycopg_async://u:p@host/db"
