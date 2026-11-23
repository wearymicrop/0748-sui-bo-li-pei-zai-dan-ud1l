from fastapi import APIRouter, Request

from app.api import preview

router = APIRouter(prefix="/api/weighing", tags=["磅单采集"])


@router.get("/{source}")
def inspect(request: Request, source: str):
    return preview(request, source)["weighing"]
