from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from pydantic import BaseModel
from app.deps import AnyTenantUser, AdminOnly, DB
from app.models import Tenant, TenantUser
from app.services.audit import log_action

router = APIRouter()


class TenantUpdate(BaseModel):
    name: str | None = None
    ai_persona_name: str | None = None
    ai_persona_voice: str | None = None
    logo_url: str | None = None


class InviteUser(BaseModel):
    email: str
    firebase_uid: str
    display_name: str | None = None
    role: str = "recruiter"  # admin|recruiter|hiring_manager|viewer


@router.get("/me")
async def get_my_tenant(user: AnyTenantUser, db: DB):
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.patch("/me")
async def update_tenant(body: TenantUpdate, user: AdminOnly, db: DB):
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one()
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(tenant, field, value)
    return tenant


@router.get("/me/users")
async def list_users(user: AnyTenantUser, db: DB):
    result = await db.execute(
        select(TenantUser).where(TenantUser.tenant_id == user.tenant_id)
    )
    return result.scalars().all()


@router.post("/me/users", status_code=status.HTTP_201_CREATED)
async def invite_user(body: InviteUser, user: AdminOnly, db: DB):
    if body.role not in {"admin", "recruiter", "hiring_manager", "viewer"}:
        raise HTTPException(status_code=422, detail="Invalid role")

    new_user = TenantUser(
        tenant_id=user.tenant_id,
        firebase_uid=body.firebase_uid,
        email=body.email,
        display_name=body.display_name,
        role=body.role,
    )
    db.add(new_user)
    await log_action(db, user, "USER_INVITED", "user", new_user.id,
                     metadata={"email": body.email, "role": body.role})
    return new_user


@router.delete("/me/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(user_id: str, user: AdminOnly, db: DB):
    result = await db.execute(
        select(TenantUser).where(TenantUser.id == user_id, TenantUser.tenant_id == user.tenant_id)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    await db.delete(target)
