from app.models import AuditLog, TenantUser
from sqlalchemy.ext.asyncio import AsyncSession


async def log_action(
    db: AsyncSession,
    user: TenantUser,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Write an immutable audit log entry (SOC 2 evidence)."""
    entry = AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata or {},
    )
    db.add(entry)
    # Intentionally not committing here — caller's transaction includes this entry.
