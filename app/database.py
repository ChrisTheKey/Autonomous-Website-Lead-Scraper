from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Strip sslmode from URL and pass SSL via connect_args (asyncpg requirement)
_db_url = settings.database_url
for _param in ("?sslmode=require", "&sslmode=require", "?ssl=true", "&ssl=true"):
    _db_url = _db_url.replace(_param, "")

_ssl_required = "neon.tech" in _db_url or "sslmode=require" in settings.database_url

engine = create_async_engine(
    _db_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"ssl": "require"} if _ssl_required else {},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
