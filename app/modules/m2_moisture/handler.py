from fastapi import APIRouter, Request

from app.api import preview

router = APIRouter(prefix="/api/moisture", tags=["含水抽样"])


@router.get("/{source}")
def inspect(request: Request, source: str):
    return preview(request, source)["moisture"]
