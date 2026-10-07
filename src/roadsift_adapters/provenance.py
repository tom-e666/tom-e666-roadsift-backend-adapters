"""Machine-readable provenance for inherited implementation ideas.

Legacy source supplied by the project owner:
P-021 development archive, commit 22cb0e700da11d0bdb4c14ed42959e327e1d397c.

The new package is a clean refactor around provider-neutral ports. It preserves selected
behavioural contracts, not the legacy application/domain schema.
"""

LEGACY_COMMIT = "22cb0e700da11d0bdb4c14ed42959e327e1d397c"
LEGACY_PATHS = {
    "execution_contracts": "src/rav05/execution/models.py",
    "kaggle_executor": "src/rav05/execution/kaggle.py",
    "artifact_store": "src/rav05/artifacts/store.py",
    "artifact_hashing": "src/rav05/artifacts/hashing.py",
    "media_store": "src/domain/storage.py",
    "db_session": "src/db/session.py",
}
NEW_IMPLEMENTATION = {
    "supabase_postgres": "src/roadsift_adapters/db/session.py",
    "r2_object_store": "src/roadsift_adapters/adapters/storage/r2.py",
    "generic_kaggle": "src/roadsift_adapters/adapters/execution/kaggle.py",
}
