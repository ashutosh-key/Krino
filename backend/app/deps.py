"""
FastAPI dependency injection: DB session, current user, RBAC guards.
"""
from __future__ import annotations
from typing import Annotated
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import verify_firebase_token
from app.models import TenantUser

bearer = HTTPBearer(auto_error=False)

# Role hierarchy (higher index = more permissions)
ROLE_LEVELS = {"viewer": 0, "hiring_manager": 1, "recruiter": 2, "admin": 3}


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantUser:
    """
    Verify Firebase JWT → look up TenantUser in DB.
    Raises 401 if token missing/invalid, 403 if user not in any tenant.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    claims = await verify_firebase_token(credentials.credentials)
    firebase_uid = claims["uid"]

    # Resolve tenant from subdomain or X-Tenant-ID header (simple: header for now)
    tenant_id = request.headers.get("X-Tenant-ID")

    q = select(TenantUser).where(TenantUser.firebase_uid == firebase_uid)
    if tenant_id:
        q = q.where(TenantUser.tenant_id == tenant_id)

    result = await db.execute(q)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not found in tenant")

    # Attach to request state for audit logging
    request.state.current_user = user
    return user


def require_role(minimum_role: str):
    """Dependency factory: require caller to have at least `minimum_role`."""
    async def _check(user: Annotated[TenantUser, Depends(get_current_user)]) -> TenantUser:
        if ROLE_LEVELS.get(user.role, -1) < ROLE_LEVELS.get(minimum_role, 99):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{minimum_role}' or higher",
            )
        return user
    return _check


# Convenience aliases
RecruiterOrAbove = Annotated[TenantUser, Depends(require_role("recruiter"))]
AdminOnly = Annotated[TenantUser, Depends(require_role("admin"))]
AnyTenantUser = Annotated[TenantUser, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]
