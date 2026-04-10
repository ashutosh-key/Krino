from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import get_settings
from app.database import engine, Base
from app.routers import health, tenants, jobs, candidates, interviews, scorecards, criteria, scout, webhooks

log = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("krino_startup", environment=settings.environment)
    # Create all tables (use Alembic migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    log.info("krino_shutdown")


app = FastAPI(
    title="Krino API",
    version="1.0.0",
    description="AI-powered video interview platform",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(tenants.router, prefix="/api/tenants", tags=["tenants"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(candidates.router, prefix="/api/candidates", tags=["candidates"])
app.include_router(interviews.router, prefix="/api/interviews", tags=["interviews"])
app.include_router(scorecards.router, prefix="/api/scorecards", tags=["scorecards"])
app.include_router(criteria.router, prefix="/api/criteria", tags=["criteria"])
app.include_router(scout.router, prefix="/api/scout", tags=["scout"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
