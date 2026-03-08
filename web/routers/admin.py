"""Admin-only API endpoints: /api/admin/*"""
import shutil
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import require_admin
from ..db.engine import get_db
from ..db.models import Job, User

router = APIRouter(prefix="/api/admin", tags=["admin"])

STORAGE_ROOT = Path("/storage")


# ── Schemas ──────────────────────────────────────────────────────────────────

class UserSummary(BaseModel):
    id: str
    email: str
    display_name: str | None
    avatar_url: str | None
    is_admin: bool
    is_active: bool
    created_at: str
    job_count: int

    model_config = {"from_attributes": True}


class UserDetail(UserSummary):
    recent_jobs: list[dict]


class PatchUserRequest(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class StatsResponse(BaseModel):
    total_users: int
    total_jobs: int
    disk_bytes: int


# ── Helpers ──────────────────────────────────────────────────────────────────

def _user_storage_bytes(user_id: str) -> int:
    path = STORAGE_ROOT / user_id
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
async def admin_stats(
    _admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_jobs  = (await db.execute(select(func.count()).select_from(Job))).scalar_one()
    disk_bytes  = sum(
        _user_storage_bytes(str(row.id))
        for row in (await db.execute(select(User.id))).scalars()
    )
    return StatsResponse(total_users=total_users, total_jobs=total_jobs, disk_bytes=disk_bytes)


@router.get("/users", response_model=list[UserSummary])
async def list_users(
    _admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
    offset: int = 0,
    limit: int = 50,
):
    # Users + job count per user
    rows = (
        await db.execute(
            select(User, func.count(Job.id).label("job_count"))
            .outerjoin(Job, Job.user_id == User.id)
            .group_by(User.id)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    return [
        UserSummary(
            id=str(u.id),
            email=u.email,
            display_name=u.display_name,
            avatar_url=u.avatar_url,
            is_admin=u.is_admin,
            is_active=u.is_active,
            created_at=u.created_at.isoformat(),
            job_count=count,
        )
        for u, count in rows
    ]


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: UUID,
    _admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.jobs))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    job_count = len(user.jobs)
    recent_jobs = [
        {
            "id": str(j.id),
            "filename": j.filename,
            "status": j.status,
            "created_at": j.created_at.isoformat(),
        }
        for j in sorted(user.jobs, key=lambda j: j.created_at, reverse=True)[:10]
    ]

    return UserDetail(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        job_count=job_count,
        recent_jobs=recent_jobs,
    )


@router.patch("/users/{user_id}", response_model=UserSummary)
async def patch_user(
    user_id: UUID,
    body: PatchUserRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    # Prevent self-demotion
    if user.id == admin.id and body.is_admin is False:
        raise HTTPException(400, "Cannot revoke your own admin rights")

    if body.is_active is not None:
        user.is_active = body.is_active
    if body.is_admin is not None:
        user.is_admin = body.is_admin

    await db.commit()
    await db.refresh(user)

    job_count = (
        await db.execute(select(func.count()).select_from(Job).where(Job.user_id == user.id))
    ).scalar_one()

    return UserSummary(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        job_count=job_count,
    )


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "Cannot delete yourself")

    # Remove storage on disk
    user_storage = STORAGE_ROOT / str(user.id)
    if user_storage.exists():
        shutil.rmtree(user_storage)

    await db.delete(user)
    await db.commit()
