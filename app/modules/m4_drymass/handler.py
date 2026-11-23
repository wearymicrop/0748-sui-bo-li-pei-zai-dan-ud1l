from fastapi import APIRouter, Request

from app.api import preview

router = APIRouter(prefix="/api/drymass", tags=["干重折算"])


@router.get("/{source}")
def inspect(request: Request, source: str):
    return preview(request, source)["drymass"]
