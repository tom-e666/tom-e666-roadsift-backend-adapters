# RoadSift Backend Adapters

Production-oriented infrastructure boundaries for the new RoadSift backend.

**Rule:** RoadSift domain/application code depends on ports. Provider SDKs stay in adapters.

\`\`\`text
FastAPI / application services
          |
          v
       Ports
    /     |      \
Postgres  R2    Compute
(Supabase)       (Kaggle)
\`\`\`

## What is implemented

- **Supabase/Postgres:** async SQLAlchemy 2 + psycopg3 engine/session factory. Supabase is treated as managed PostgreSQL, not as a domain SDK.
- **Cloudflare R2:** S3-compatible \`ObjectStore\` adapter with safe object keys, atomic local download, HEAD/exists, metadata, and presigned GET.
- **Kaggle:** provider-neutral \`ComputeExecutor\` implementation using the official Kaggle CLI. Kaggle is ephemeral compute and never the source of truth.
- **Portable JobSpec:** rejects credential-like fields before jobs can be serialized.
- **Provenance:** explicit mapping back to the supplied P-021 legacy paths and baseline commit.

## Production boundaries

- **Supabase/Postgres = relational state / metadata / lineage.**
- **R2 = large bytes and immutable artifacts.**
- **Kaggle = disposable compute.**
- A Kaggle worker should not directly mutate Supabase business state. Controller/application code validates outputs first, then commits state.
- Secrets never belong in \`JobSpec\`, artifact metadata, or checked-in configuration.
- Use Alembic for production schema migrations; do not rely on \`Base.metadata.create_all()\` at API startup.

## Install

\`\`\`bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e ".[dev,kaggle]"
cp .env.example .env
pytest
\`\`\`

## FastAPI wiring example

\`\`\`python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from roadsift_adapters.config import get_settings
from roadsift_adapters.db.session import create_database_engine, create_session_factory, session_dependency

settings = get_settings()
engine = create_database_engine(settings.DATABASE_URL)
SessionFactory = create_session_factory(engine)

async def get_db():
    async for session in session_dependency(SessionFactory):
        yield session
\`\`\`

## R2 wiring

\`\`\`python
from roadsift_adapters.factory import build_r2
from roadsift_adapters.config import get_settings

store = build_r2(get_settings())
store.put_file("frame.jpg", key="raw/project-1/run-1/frame.jpg", if_absent=True)
url = store.presign_get("raw/project-1/run-1/frame.jpg")
\`\`\`

## Kaggle wiring

\`\`\`python
from roadsift_adapters.adapters.execution.kaggle import KaggleExecutor
from roadsift_adapters.ports.executor import JobSpec

executor = KaggleExecutor(
    kernel_slug="owner/roadsift-mining",
    project_root="./worker_project",
    accelerator="gpu",
)

spec = JobSpec(
    job_id="job-001",
    job_type="mining",
    command=["python", "scripts/run_mining.py"],
    outputs={"selection": "selection.json"},
)
handle = executor.submit(spec, ".runtime/job-001")
\`\`\`

## Legacy provenance

See [\`docs/PROVENANCE.md\`](docs/PROVENANCE.md). The scaffold deliberately reuses selected design contracts from the supplied P-021 development archive rather than copying the old application schema/UI contracts.
