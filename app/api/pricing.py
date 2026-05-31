from fastapi import APIRouter, Depends, Query
from app.auth.dependencies import get_current_user
from app.auth.roles import require_admin
from app.models.user import User
from app.services.pricing_service import (
    get_azure_pricing,
    get_aws_pricing,
    invalidate_cache,
)

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("/azure/{region}")
def azure_catalog(
    region: str = "eastus",
    _: User = Depends(get_current_user),
):
    """Return the Azure cloud pricing catalog for a region (cached 24h)."""
    return get_azure_pricing(region)


@router.get("/azure")
def azure_catalog_default(_: User = Depends(get_current_user)):
    return get_azure_pricing("eastus")


@router.get("/aws/{region}")
def aws_catalog(
    region: str = "us-east-1",
    _: User = Depends(get_current_user),
):
    """Return the AWS cloud pricing catalog for a region."""
    return get_aws_pricing(region)


@router.get("/aws")
def aws_catalog_default(_: User = Depends(get_current_user)):
    return get_aws_pricing("us-east-1")


@router.post("/refresh")
def refresh_pricing_cache(
    provider: str | None = Query(None, description="'aws' or 'azure'; omit for all"),
    _: User = Depends(require_admin),
):
    """Force a cache refresh on the next pricing request. Admin only."""
    invalidate_cache(provider)
    return {"invalidated": provider or "all"}
