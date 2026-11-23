from fastapi import APIRouter, Request

from app.api import preview

router = APIRouter(prefix="/api/loading", tags=["目标配载"])


@router.get("/{source}")
def inspect(request: Request, source: str):
    return preview(request, source)["loading"]
