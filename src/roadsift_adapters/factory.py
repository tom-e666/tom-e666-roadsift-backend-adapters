from roadsift_adapters.adapters.storage.r2 import R2ObjectStore
from roadsift_adapters.config import Settings
from roadsift_adapters.db.session import create_database_engine, create_session_factory


def build_r2(settings: Settings) -> R2ObjectStore:
    return R2ObjectStore(
        account_id=settings.R2_ACCOUNT_ID,
        access_key_id=settings.R2_ACCESS_KEY_ID.get_secret_value(),
        secret_access_key=settings.R2_SECRET_ACCESS_KEY.get_secret_value(),
        bucket=settings.R2_BUCKET,
        region=settings.R2_REGION,
        presign_ttl_seconds=settings.R2_PRESIGN_TTL_SECONDS,
    )


def build_database(settings: Settings):
    engine = create_database_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle_seconds=settings.DB_POOL_RECYCLE_SECONDS,
    )
    return engine, create_session_factory(engine)
