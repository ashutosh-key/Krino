from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Strip sslmode/channel_binding params that asyncpg doesn't accept,
# then pass ssl=True for Neon / production TLS
def _make_engine_url(raw: str) -> tuple[str, dict]:
    # SQLite URLs have sqlite+aiosqlite:///./path — skip query munging
    if raw.startswith("sqlite"):
        return raw, {}
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
    parsed = urlparse(raw)
    qs = parse_qs(parsed.query)
    qs.pop("sslmode", None)
    qs.pop("channel_binding", None)
    clean_qs = urlencode({k: v[0] for k, v in qs.items()})
    clean_url = urlunparse(parsed._replace(query=clean_qs))
    connect_args = {}
    if settings.is_production:
        connect_args["ssl"] = True
    return clean_url, connect_args


_url, _connect_args = _make_engine_url(settings.database_url)

_is_sqlite = _url.startswith("sqlite")
engine = create_async_engine(
    _url,
    echo=not settings.is_production,
    **({} if _is_sqlite else {"pool_size": 10, "max_overflow": 20}),
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
