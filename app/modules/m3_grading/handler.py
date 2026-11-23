from fastapi import APIRouter, Request

from app.api import preview

router = APIRouter(prefix="/api/grading", tags=["色级判定"])


@router.get("/{source}")
def inspect(request: Request, source: str):
    return preview(request, source)["grading"]
